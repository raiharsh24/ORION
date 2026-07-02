import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable
from loguru import logger

from app.events.bus import EventBus
from app.tool_execution.executor import ToolExecutionEngine, CancellationToken
from app.tool_execution.base import (
    ExecutionMode, ExecutionContext, ExecutionStatus as ToolExecStatus,
)
from app.tool_selection.base import ToolSelectionResult, SelectedTool
from app.tools.base import ToolDefinition
from app.workflow_engine.base import (
    WorkflowGraph, WorkflowNode, WorkflowNodeType, WorkflowStatus,
    WorkflowEdge, WorkflowContext, ExecutedNode, WorkflowExecutionResult,
)
from app.workflow_engine.events import (
    WorkflowStarted, WorkflowNodeStarted, WorkflowNodeCompleted,
    WorkflowCompleted, WorkflowFailed, WorkflowCancelled,
)
from app.workflow_engine.graph import WorkflowGraphBuilder, WorkflowValidator
from app.workflow_engine.result import build_workflow_report


class WorkflowExecutor:
    def __init__(
        self,
        tool_execution_engine: ToolExecutionEngine,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._tool_engine = tool_execution_engine
        self._event_bus = event_bus
        self._execution_count = 0
        self._failure_count = 0
        self._cancellation_count = 0
        self._total_latency_ms = 0.0

    async def execute(
        self,
        graph: WorkflowGraph,
        global_timeout: float = 120.0,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> WorkflowExecutionResult:
        execution_id = str(uuid.uuid4())
        t0 = time.time()
        token = cancellation_token or CancellationToken()

        errors = WorkflowValidator.validate(graph)
        if errors:
            return WorkflowExecutionResult(
                execution_id=execution_id,
                status=WorkflowStatus.FAILED,
                error=f"Graph validation failed: {errors[0]}",
                errors=errors,
            )

        context = WorkflowContext(execution_id=execution_id)
        node_results: Dict[str, ExecutedNode] = {
            nid: ExecutedNode(node_id=nid) for nid in graph.nodes
        }

        self._publish(WorkflowStarted(
            execution_id=execution_id,
            graph_id=graph.metadata.get("id", "anonymous"),
            total_nodes=len(graph.nodes),
        ))

        layers = WorkflowGraphBuilder.topological_sort(graph)

        for layer in layers:
            if token.cancelled:
                for nid in layer:
                    self._fail_node(node_results[nid], "Workflow cancelled")
                    node_results[nid].status = WorkflowStatus.CANCELLED
                    context.error = "Workflow cancelled"
                self._publish(WorkflowCancelled(
                    execution_id=execution_id, reason="Workflow cancelled",
                ))
                break

            for nid in layer:
                node = graph.nodes.get(nid)
                if node is None:
                    continue
                en = node_results[nid]

                if node.node_type == WorkflowNodeType.TOOL:
                    await self._execute_tool_node(node, en, context, execution_id, token, global_timeout)
                elif node.node_type == WorkflowNodeType.CONDITION:
                    self._evaluate_condition(node, en, context)
                elif node.node_type == WorkflowNodeType.PARALLEL:
                    await self._execute_parallel_branches(node, en, context, execution_id, token, global_timeout, graph)
                elif node.node_type == WorkflowNodeType.MERGE:
                    en.status = WorkflowStatus.COMPLETED
                    en.completed_at = datetime.now(timezone.utc)
                else:
                    en.status = WorkflowStatus.SKIPPED

                if en.status == WorkflowStatus.FAILED:
                    self._publish(WorkflowFailed(
                        execution_id=execution_id,
                        node_id=nid,
                        error=en.error or "Unknown error",
                    ))
                    if not self._should_continue_on_failure(graph, nid):
                        for remaining_nid in [rn for rn in graph.nodes if rn not in node_results or node_results[rn].status == WorkflowStatus.PENDING]:
                            nr = node_results.get(remaining_nid)
                            if nr and nr.status == WorkflowStatus.PENDING:
                                nr.status = WorkflowStatus.SKIPPED
                        result = build_workflow_report(node_results, context, (time.time() - t0) * 1000)
                        result.status = WorkflowStatus.FAILED
                        self._publish(WorkflowCompleted(
                            execution_id=execution_id,
                            status="failed",
                            total_duration_ms=result.total_duration_ms,
                            total_nodes=len(graph.nodes),
                        ))
                        self._execution_count += 1
                        self._failure_count += 1
                        self._total_latency_ms += result.total_duration_ms
                        return result

        result = build_workflow_report(node_results, context, (time.time() - t0) * 1000)
        self._publish(WorkflowCompleted(
            execution_id=execution_id,
            status=result.status.value,
            total_duration_ms=result.total_duration_ms,
            total_nodes=len(graph.nodes),
        ))

        self._execution_count += 1
        self._total_latency_ms += result.total_duration_ms

        return result

    async def _execute_tool_node(
        self,
        node: WorkflowNode,
        en: ExecutedNode,
        context: WorkflowContext,
        execution_id: str,
        token: CancellationToken,
        global_timeout: float,
    ) -> None:
        self._publish(WorkflowNodeStarted(
            execution_id=execution_id,
            node_id=node.id,
            node_type=node.node_type.value,
            tool_id=node.tool_id,
        ))
        en.started_at = datetime.now(timezone.utc)
        en.status = WorkflowStatus.RUNNING

        try:
            tool_def = ToolDefinition(
                id=node.tool_id,
                name=node.name or node.tool_id,
                description="",
                category=node.metadata.get("category", ""),
                estimated_latency_ms=node.timeout * 1000,
            )
            selection = ToolSelectionResult(selected_tools=[
                SelectedTool(tool=tool_def, score=1.0, selection_reason="workflow"),
            ])

            exec_result = await self._tool_engine.execute(
                selection_result=selection,
                args_overrides={node.tool_id: dict(node.args)},
                mode=ExecutionMode.SEQUENTIAL,
                global_timeout=min(node.timeout, global_timeout),
                cancellation_token=token,
            )

            et = exec_result.results[0] if exec_result.results else None
            if et is None:
                en.status = WorkflowStatus.FAILED
                en.error = "No execution result returned"
            elif et.status == ToolExecStatus.COMPLETED:
                en.status = WorkflowStatus.COMPLETED
                en.output = et.output
                context.shared_data[node.id] = et.output
                context.node_outputs[node.id] = et.output
            elif et.status == ToolExecStatus.TIMEOUT:
                en.status = WorkflowStatus.FAILED
                en.error = et.error or "Tool timed out"
            elif et.status == ToolExecStatus.CANCELLED:
                en.status = WorkflowStatus.CANCELLED
                en.error = et.error or "Tool cancelled"
            else:
                en.status = WorkflowStatus.FAILED
                en.error = et.error or f"Tool execution failed with status {et.status.value}"

            en.duration_ms = et.duration_ms
            en.retries = et.retries

        except Exception as e:
            en.status = WorkflowStatus.FAILED
            en.error = str(e)

        en.completed_at = datetime.now(timezone.utc)
        self._publish(WorkflowNodeCompleted(
            execution_id=execution_id,
            node_id=node.id,
            status=en.status.value,
            duration_ms=en.duration_ms,
        ))

    def _evaluate_condition(
        self,
        node: WorkflowNode,
        en: ExecutedNode,
        context: WorkflowContext,
    ) -> None:
        en.started_at = datetime.now(timezone.utc)
        if node.condition is not None:
            try:
                result = node.condition(context.shared_data)
                en.output = result
                en.status = WorkflowStatus.COMPLETED
            except Exception as e:
                en.status = WorkflowStatus.FAILED
                en.error = str(e)
        else:
            en.output = True
            en.status = WorkflowStatus.COMPLETED
        en.completed_at = datetime.now(timezone.utc)

    async def _execute_parallel_branches(
        self,
        node: WorkflowNode,
        en: ExecutedNode,
        context: WorkflowContext,
        execution_id: str,
        token: CancellationToken,
        global_timeout: float,
        graph: WorkflowGraph,
    ) -> None:
        en.started_at = datetime.now(timezone.utc)
        en.status = WorkflowStatus.RUNNING

        branches = node.parallel_branches or []
        if not branches:
            children = graph.get_children(node.id)
            branches = [[c] for c in children]

        branch_tasks = []
        for branch in branches:
            for bid in branch:
                child_node = graph.nodes.get(bid)
                if child_node and child_node.node_type == WorkflowNodeType.TOOL:
                    child_en = ExecutedNode(node_id=bid)
                    branch_tasks.append(
                        self._execute_tool_node(child_node, child_en, context, execution_id, token, global_timeout)
                    )

        if branch_tasks:
            await asyncio.gather(*branch_tasks, return_exceptions=True)

        en.status = WorkflowStatus.COMPLETED
        en.completed_at = datetime.now(timezone.utc)

    def _should_continue_on_failure(self, graph: WorkflowGraph, failed_node_id: str) -> bool:
        node = graph.nodes.get(failed_node_id)
        if node and node.metadata.get("continue_on_failure", False):
            return True
        return False

    def cancel(self, execution_id: str) -> None:
        logger.info(f"Cancellation requested for workflow {execution_id}")

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "execution_count": self._execution_count,
            "failure_count": self._failure_count,
            "cancellation_count": self._cancellation_count,
            "average_latency_ms": round(
                self._total_latency_ms / max(self._execution_count, 1), 2
            ),
        }

    def _fail_node(self, en: ExecutedNode, error: str) -> None:
        en.status = WorkflowStatus.FAILED
        en.error = error
        en.completed_at = datetime.now(timezone.utc)

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
