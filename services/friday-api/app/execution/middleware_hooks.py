from typing import Any, Optional
from loguru import logger

from app.execution.context import ExecutionContext, Stage
from app.execution.middleware import ExecutionMiddleware


class PluginHookMiddleware(ExecutionMiddleware):
    def __init__(self, plugin_runtime: Optional[Any] = None) -> None:
        self._plugin_runtime = plugin_runtime

    async def before_planning(self, ctx: ExecutionContext) -> None:
        if self._plugin_runtime:
            await self._run_plugin_hooks(ctx, "before_planning")

    async def after_planning(self, ctx: ExecutionContext) -> None:
        if self._plugin_runtime:
            await self._run_plugin_hooks(ctx, "after_planning")

    async def before_execution(self, ctx: ExecutionContext) -> None:
        if self._plugin_runtime:
            await self._run_plugin_hooks(ctx, "before_execution")

    async def after_execution(self, ctx: ExecutionContext) -> None:
        if self._plugin_runtime:
            await self._run_plugin_hooks(ctx, "after_execution")

    async def before_response(self, ctx: ExecutionContext) -> None:
        if self._plugin_runtime:
            await self._run_plugin_hooks(ctx, "before_response")

    async def _run_plugin_hooks(self, ctx: ExecutionContext, hook: str) -> None:
        for plugin_id, inst in self._plugin_runtime._loader.instances.items():
            if not hasattr(inst, "plugin") or not hasattr(inst.plugin, hook):
                continue
            try:
                await self._plugin_runtime.execute(
                    plugin_id=plugin_id,
                    coro=getattr(inst.plugin, hook)(ctx),
                    timeout_ms=5000,
                )
            except Exception as e:
                logger.debug(f"Plugin {plugin_id} {hook} hook failed: {e}")


class MemoryUpdateMiddleware(ExecutionMiddleware):
    async def after_execution(self, ctx: ExecutionContext) -> None:
        if ctx.tool_used and ctx.tool_output:
            session = ctx.metadata.get("_session")
            if session:
                session.tool_used = ctx.tool_used
                session.tool_output = ctx.tool_output

    async def after_response(self, ctx: ExecutionContext) -> None:
        pass  # handled by engine itself


class MetricsCaptureMiddleware(ExecutionMiddleware):
    def __init__(self, metrics: Any) -> None:
        self._metrics = metrics

    async def on_error(self, ctx: ExecutionContext, stage: Stage, error: Exception) -> None:
        if self._metrics:
            self._metrics.record_stage(stage.value, 0.0, error=str(error))
