import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable
from loguru import logger

from app.events.bus import EventBus
from app.friday.tool_registry import ToolRegistry as LegacyToolRegistry
from app.tools.registry import ToolRegistry as UniversalToolRegistry
from app.tools.base import ToolDefinition, PermissionLevel
from app.tool_selection.base import ToolSelectionResult, SelectedTool
from app.tool_execution.base import (
    ExecutionMode, ExecutionStatus, ExecutionContext, ExecutedTool,
    ToolExecutionResult, ExecutionReport,
)
from app.tool_execution.events import (
    ToolExecutionStarted, ToolExecutionCompleted,
    ToolExecutionFailed, ToolExecutionCancelled,
)
from app.tool_execution.result import build_report
from app.tool_execution.scheduler import ExecutionScheduler


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class ToolExecutionEngine:
    def __init__(
        self,
        legacy_tool_registry: LegacyToolRegistry,
        universal_tool_registry: Optional[UniversalToolRegistry] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._legacy_registry = legacy_tool_registry
        self._universal_registry = universal_tool_registry
        self._event_bus = event_bus
        self._execution_count = 0
        self._failure_count = 0
        self._timeout_count = 0
        self._retry_count = 0
        self._total_latency_ms = 0.0
        self._cancellation_tokens: Dict[str, CancellationToken] = {}

    async def execute(
        self,
        selection_result: ToolSelectionResult,
        args_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        dependency_map: Optional[Dict[str, List[str]]] = None,
        global_timeout: float = 120.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> ToolExecutionResult:
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        token = cancellation_token or CancellationToken()

        contexts = self._build_contexts(
            selection_result, args_overrides or {},
        )
        layers = ExecutionScheduler.order_tools(contexts, mode, dependency_map or {})

        result = ToolExecutionResult(
            execution_id=execution_id,
            mode=mode,
        )

        all_results: List[ExecutedTool] = []
        for layer in layers:
            if token.cancelled:
                for ctx in layer:
                    all_results.append(ExecutedTool(
                        tool_id=ctx.tool_id,
                        status=ExecutionStatus.CANCELLED,
                        error="Execution cancelled",
                    ))
                    self._publish(ToolExecutionCancelled(
                        execution_id=execution_id,
                        tool_id=ctx.tool_id,
                        reason="Execution cancelled",
                    ))
                break

            self._publish(ToolExecutionStarted(
                execution_id=execution_id,
                tool_id=",".join(c.tool_id for c in layer),
                mode=mode.value,
                total_tools=len(contexts),
            ))

            if len(layer) == 1 or mode == ExecutionMode.SEQUENTIAL:
                for ctx in layer:
                    et = await self._execute_single(ctx, execution_id, token, global_timeout)
                    all_results.append(et)
            else:
                tasks = [
                    self._execute_single(ctx, execution_id, token, global_timeout)
                    for ctx in layer
                ]
                done = await asyncio.gather(*tasks, return_exceptions=True)
                for et in done:
                    if isinstance(et, ExecutedTool):
                        all_results.append(et)
                    else:
                        all_results.append(ExecutedTool(
                            tool_id="unknown",
                            status=ExecutionStatus.FAILED,
                            error=str(et) if et else "Unknown error",
                        ))

        result.results = all_results
        result.report = build_report(all_results)
        result.status = ExecutionStatus.COMPLETED

        self._execution_count += 1
        self._total_latency_ms += (time.time() - start_time) * 1000

        return result

    async def _execute_single(
        self,
        ctx: ExecutionContext,
        execution_id: str,
        token: CancellationToken,
        global_timeout: float,
    ) -> ExecutedTool:
        started = datetime.now(timezone.utc)
        tool = self._get_tool_instance(ctx.tool_id)
        if tool is None:
            return ExecutedTool(
                tool_id=ctx.tool_id,
                status=ExecutionStatus.FAILED,
                error=f"Tool '{ctx.tool_id}' not found in execution registry",
                started_at=started,
                completed_at=datetime.now(timezone.utc),
            )

        if self._universal_registry:
            td = self._universal_registry.get(ctx.tool_id)
            if td is None:
                return ExecutedTool(
                    tool_id=ctx.tool_id,
                    status=ExecutionStatus.FAILED,
                    error=f"Tool '{ctx.tool_id}' not found in universal registry",
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                )

        et = ExecutedTool(
            tool_id=ctx.tool_id,
            status=ExecutionStatus.RUNNING,
            started_at=started,
            timeout_seconds=min(ctx.timeout, global_timeout),
        )

        effective_timeout = min(ctx.timeout, global_timeout)
        attempt = 0
        max_retries = ctx.max_retries

        while attempt <= max_retries:
            if token.cancelled:
                et.status = ExecutionStatus.CANCELLED
                et.error = "Cancelled by user"
                et.completed_at = datetime.now(timezone.utc)
                self._publish(ToolExecutionCancelled(
                    execution_id=execution_id,
                    tool_id=ctx.tool_id,
                    reason="Cancelled by user",
                ))
                return et

            attempt += 1
            t0 = time.time()
            try:
                output = await asyncio.wait_for(
                    tool.execute(**ctx.args),
                    timeout=effective_timeout,
                )
                et.status = ExecutionStatus.COMPLETED
                et.output = output
                et.duration_ms = (time.time() - t0) * 1000
                et.completed_at = datetime.now(timezone.utc)
                et.retries = attempt - 1
                self._publish(ToolExecutionCompleted(
                    execution_id=execution_id,
                    tool_id=ctx.tool_id,
                    duration_ms=et.duration_ms,
                    output=str(output) if output else "",
                ))
                return et

            except asyncio.TimeoutError as tout:
                self._timeout_count += 1
                if attempt <= max_retries:
                    self._retry_count += 1
                    await asyncio.sleep(ctx.retry_delay)
                    continue
                et.status = ExecutionStatus.TIMEOUT
                et.error = f"Timed out after {effective_timeout}s"
                et.duration_ms = (time.time() - t0) * 1000
                et.completed_at = datetime.now(timezone.utc)
                et.retries = attempt - 1
                self._publish(ToolExecutionFailed(
                    execution_id=execution_id,
                    tool_id=ctx.tool_id,
                    error=et.error,
                    retries=attempt - 1,
                ))
                return et

            except Exception as e:
                self._failure_count += 1
                if attempt <= max_retries:
                    self._retry_count += 1
                    await asyncio.sleep(ctx.retry_delay)
                    continue
                et.status = ExecutionStatus.FAILED
                et.error = str(e)
                et.duration_ms = (time.time() - t0) * 1000
                et.completed_at = datetime.now(timezone.utc)
                et.retries = attempt - 1
                self._publish(ToolExecutionFailed(
                    execution_id=execution_id,
                    tool_id=ctx.tool_id,
                    error=str(e),
                    retries=attempt - 1,
                ))
                return et

    def cancel(self, execution_id: str) -> None:
        if execution_id == "__all__":
            for token in self._cancellation_tokens.values():
                token.cancel()
        elif execution_id in self._cancellation_tokens:
            self._cancellation_tokens[execution_id].cancel()

    def _get_tool_instance(self, tool_id: str) -> Any:
        return self._legacy_registry.get(tool_id)

    def _build_contexts(
        self,
        selection_result: ToolSelectionResult,
        args_overrides: Dict[str, Dict[str, Any]],
    ) -> List[ExecutionContext]:
        contexts = []
        for st in selection_result.selected_tools:
            tool_id = st.tool.id
            args = dict(args_overrides.get(tool_id, {}))
            contexts.append(ExecutionContext(
                tool_id=tool_id,
                args=args,
                timeout=getattr(st.tool, "estimated_latency_ms", 30.0) / 1000.0 + 5.0,
            ))
        return contexts

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "execution_count": self._execution_count,
            "failure_count": self._failure_count,
            "timeout_count": self._timeout_count,
            "retry_count": self._retry_count,
            "average_latency_ms": round(
                self._total_latency_ms / max(self._execution_count, 1), 2
            ),
        }

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
