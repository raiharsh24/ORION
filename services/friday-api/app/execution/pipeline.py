import asyncio
import time
from typing import Any, Optional, Dict, List
from loguru import logger

from app.execution.context import ExecutionContext, Stage, StageStatus, CancelledError
from app.execution.config import ExecutionConfig, RetryPolicy
from app.execution.middleware import MiddlewareChain
from app.execution.metrics import ExecutionMetrics
from app.execution.events import (
    StageStarted, StageCompleted, StageFailed,
    ExecutionProgress,
)


class StageRunner:
    def __init__(
        self,
        stage: Stage,
        handler: Any,
        config: ExecutionConfig,
        middleware: MiddlewareChain,
        metrics: ExecutionMetrics,
    ) -> None:
        self._stage = stage
        self._handler = handler
        self._config = config
        self._middleware = middleware
        self._metrics = metrics

    async def run(self, ctx: ExecutionContext) -> None:
        if ctx.cancelled:
            ctx.skip_stage(self._stage, "Execution cancelled")
            return

        retry_policy = self._config.retry_policy
        timeout = self._get_timeout()
        last_error: Optional[Exception] = None

        for attempt in range(retry_policy.max_retries + 1):
            if ctx.cancelled:
                ctx.skip_stage(self._stage, "Execution cancelled")
                return

            try:
                ctx.start_stage(self._stage)

                before_hook = getattr(self._middleware, f"before_{self._stage.value}")
                after_hook = getattr(self._middleware, f"after_{self._stage.value}")

                if attempt > 0:
                    self._metrics.record_retry()
                    delay = min(
                        retry_policy.base_delay_ms * (retry_policy.backoff_multiplier ** (attempt - 1)),
                        retry_policy.max_delay_ms,
                    ) / 1000.0
                    logger.info(f"Retrying {self._stage.value} (attempt {attempt + 1}) after {delay:.1f}s")
                    await asyncio.sleep(delay)

                await before_hook(ctx)
                result = await asyncio.wait_for(
                    self._handler(ctx),
                    timeout=timeout,
                )
                ctx.complete_stage(self._stage, result)
                await after_hook(ctx)
                return

            except asyncio.TimeoutError:
                last_error = TimeoutError(f"{self._stage.value} timed out after {timeout}s")
                ctx.fail_stage(self._stage, str(last_error))
                await self._middleware.on_error(ctx, self._stage, last_error)
                if attempt < retry_policy.max_retries:
                    ctx.stage_records[self._stage.value].status = StageStatus.RUNNING
                    continue

            except CancelledError:
                ctx.stage_records[self._stage.value].status = StageStatus.CANCELLED
                return

            except Exception as e:
                last_error = e
                ctx.fail_stage(self._stage, str(e))
                await self._middleware.on_error(ctx, self._stage, e)
                if attempt < retry_policy.max_retries:
                    ctx.stage_records[self._stage.value].status = StageStatus.RUNNING
                    continue

        if last_error:
            raise last_error

    def _get_timeout(self) -> float:
        timeout_config = self._config.timeout_policy
        stage_key = f"{self._stage.value}_timeout_s"
        return getattr(timeout_config, stage_key, 30.0)


class ExecutionPipeline:
    def __init__(
        self,
        config: ExecutionConfig,
        middleware: MiddlewareChain,
        metrics: ExecutionMetrics,
    ) -> None:
        self._config = config
        self._middleware = middleware
        self._metrics = metrics
        self._runners: Dict[Stage, StageRunner] = {}
        self._on_progress: List[Any] = []

    def register_stage(self, stage: Stage, handler: Any) -> None:
        self._runners[stage] = StageRunner(
            stage=stage,
            handler=handler,
            config=self._config,
            middleware=self._middleware,
            metrics=self._metrics,
        )

    def on_progress(self, callback: Any) -> None:
        self._on_progress.append(callback)

    async def _emit_progress(self, ctx: ExecutionContext, stage: Stage, pct: float, msg: str = "") -> None:
        if not self._config.emit_events:
            return
        event = ExecutionProgress(
            execution_id=ctx.execution_id,
            stage=stage.value,
            progress_pct=pct,
            message=msg or f"Stage: {stage.value}",
        )
        for cb in self._on_progress:
            try:
                await cb(event)
            except Exception:
                pass

    async def execute(self, ctx: ExecutionContext) -> None:
        stages = [
            Stage.PLANNING,
            Stage.MEMORY,
            Stage.TOOL_SELECTION,
            Stage.EXECUTION,
            Stage.ENRICHMENT,
            Stage.LLM,
            Stage.RESPONSE,
        ]

        total = len(stages)

        for idx, stage in enumerate(stages):
            if ctx.cancelled:
                await self._middleware.on_cancel(ctx)
                raise CancelledError("Execution cancelled")

            runner = self._runners.get(stage)
            if runner is None:
                ctx.skip_stage(stage, "No handler registered")
                continue

            pct = (idx / total) * 100.0
            await self._emit_progress(ctx, stage, pct)

            try:
                await runner.run(ctx)
            except Exception as e:
                logger.error(f"Pipeline stage {stage.value} failed: {e}")
                await self._middleware.on_error(ctx, stage, e)
                return

            pct = ((idx + 1) / total) * 100.0
            await self._emit_progress(ctx, stage, pct, f"Completed: {stage.value}")

    @property
    def config(self) -> ExecutionConfig:
        return self._config
