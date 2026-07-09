import time
from typing import Any, Dict, List, Optional, Callable, Awaitable
from loguru import logger

from app.execution.context import ExecutionContext, Stage
from app.execution.metrics import ExecutionMetrics


class ExecutionMiddleware:
    async def before_intent(self, ctx: ExecutionContext) -> None:
        pass

    async def after_intent(self, ctx: ExecutionContext) -> None:
        pass

    async def before_planning(self, ctx: ExecutionContext) -> None:
        pass

    async def after_planning(self, ctx: ExecutionContext) -> None:
        pass

    async def before_memory(self, ctx: ExecutionContext) -> None:
        pass

    async def after_memory(self, ctx: ExecutionContext) -> None:
        pass

    async def before_tool_selection(self, ctx: ExecutionContext) -> None:
        pass

    async def after_tool_selection(self, ctx: ExecutionContext) -> None:
        pass

    async def before_execution(self, ctx: ExecutionContext) -> None:
        pass

    async def after_execution(self, ctx: ExecutionContext) -> None:
        pass

    async def before_enrichment(self, ctx: ExecutionContext) -> None:
        pass

    async def after_enrichment(self, ctx: ExecutionContext) -> None:
        pass

    async def before_llm(self, ctx: ExecutionContext) -> None:
        pass

    async def after_llm(self, ctx: ExecutionContext) -> None:
        pass

    async def before_response(self, ctx: ExecutionContext) -> None:
        pass

    async def after_response(self, ctx: ExecutionContext) -> None:
        pass

    async def on_error(self, ctx: ExecutionContext, stage: Stage, error: Exception) -> None:
        pass

    async def on_cancel(self, ctx: ExecutionContext) -> None:
        pass


class LoggingMiddleware(ExecutionMiddleware):
    async def before_intent(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Intent classification started")

    async def after_intent(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Intent: {ctx.intent}")

    async def before_planning(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Planning started")

    async def after_planning(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Plan: {getattr(ctx.plan, 'tool_name', None) or 'none'}")

    async def before_memory(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Memory retrieval started")

    async def before_tool_selection(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Tool selection started")

    async def before_execution(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Execution started")

    async def after_execution(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] Tool used: {ctx.tool_used}")

    async def before_llm(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] LLM generation started")

    async def after_llm(self, ctx: ExecutionContext) -> None:
        logger.info(f"[{ctx.execution_id[:8]}] LLM response received")

    async def on_error(self, ctx: ExecutionContext, stage: Stage, error: Exception) -> None:
        logger.error(f"[{ctx.execution_id[:8]}] Error in {stage.value}: {error}")


class MetricsMiddleware(ExecutionMiddleware):
    def __init__(self, metrics: ExecutionMetrics) -> None:
        self._metrics = metrics

    async def after_intent(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.INTENT.value]
        self._metrics.record_stage(Stage.INTENT.value, r.duration_ms)

    async def after_planning(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.PLANNING.value]
        self._metrics.record_stage(Stage.PLANNING.value, r.duration_ms,
                                     error=r.error)

    async def after_memory(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.MEMORY.value]
        self._metrics.record_stage(Stage.MEMORY.value, r.duration_ms,
                                     error=r.error)

    async def after_tool_selection(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.TOOL_SELECTION.value]
        self._metrics.record_stage(Stage.TOOL_SELECTION.value, r.duration_ms,
                                     error=r.error)

    async def after_execution(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.EXECUTION.value]
        self._metrics.record_stage(Stage.EXECUTION.value, r.duration_ms,
                                     error=r.error)

    async def after_enrichment(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.ENRICHMENT.value]
        self._metrics.record_stage(Stage.ENRICHMENT.value, r.duration_ms)

    async def after_llm(self, ctx: ExecutionContext) -> None:
        r = ctx.stage_records[Stage.LLM.value]
        self._metrics.record_stage(Stage.LLM.value, r.duration_ms,
                                     error=r.error)

    async def on_error(self, ctx: ExecutionContext, stage: Stage, error: Exception) -> None:
        self._metrics.record_stage(stage.value, 0.0, error=str(error))


class MiddlewareChain:
    def __init__(self, middlewares: Optional[List[ExecutionMiddleware]] = None) -> None:
        self._middlewares: List[ExecutionMiddleware] = middlewares or []

    def add(self, middleware: ExecutionMiddleware) -> None:
        self._middlewares.append(middleware)

    def remove(self, middleware: ExecutionMiddleware) -> None:
        self._middlewares.remove(middleware)

    async def _apply(self, hook: str, ctx: ExecutionContext, *args, **kwargs) -> None:
        for mw in self._middlewares:
            method = getattr(mw, hook, None)
            if method:
                await method(ctx, *args, **kwargs)

    async def before_intent(self, ctx: ExecutionContext) -> None:
        await self._apply("before_intent", ctx)

    async def after_intent(self, ctx: ExecutionContext) -> None:
        await self._apply("after_intent", ctx)

    async def before_planning(self, ctx: ExecutionContext) -> None:
        await self._apply("before_planning", ctx)

    async def after_planning(self, ctx: ExecutionContext) -> None:
        await self._apply("after_planning", ctx)

    async def before_memory(self, ctx: ExecutionContext) -> None:
        await self._apply("before_memory", ctx)

    async def after_memory(self, ctx: ExecutionContext) -> None:
        await self._apply("after_memory", ctx)

    async def before_tool_selection(self, ctx: ExecutionContext) -> None:
        await self._apply("before_tool_selection", ctx)

    async def after_tool_selection(self, ctx: ExecutionContext) -> None:
        await self._apply("after_tool_selection", ctx)

    async def before_execution(self, ctx: ExecutionContext) -> None:
        await self._apply("before_execution", ctx)

    async def after_execution(self, ctx: ExecutionContext) -> None:
        await self._apply("after_execution", ctx)

    async def before_enrichment(self, ctx: ExecutionContext) -> None:
        await self._apply("before_enrichment", ctx)

    async def after_enrichment(self, ctx: ExecutionContext) -> None:
        await self._apply("after_enrichment", ctx)

    async def before_llm(self, ctx: ExecutionContext) -> None:
        await self._apply("before_llm", ctx)

    async def after_llm(self, ctx: ExecutionContext) -> None:
        await self._apply("after_llm", ctx)

    async def before_response(self, ctx: ExecutionContext) -> None:
        await self._apply("before_response", ctx)

    async def after_response(self, ctx: ExecutionContext) -> None:
        await self._apply("after_response", ctx)

    async def on_error(self, ctx: ExecutionContext, stage: Stage, error: Exception) -> None:
        await self._apply("on_error", ctx, stage, error)

    async def on_cancel(self, ctx: ExecutionContext) -> None:
        await self._apply("on_cancel", ctx)
