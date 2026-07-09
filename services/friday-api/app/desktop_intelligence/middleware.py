from typing import Any, Optional
from loguru import logger

from app.execution.middleware import ExecutionMiddleware
from app.execution.context import ExecutionContext


class DesktopContextMiddleware(ExecutionMiddleware):
    def __init__(self, desktop_intelligence: Any = None) -> None:
        self._di = desktop_intelligence

    def set_desktop_intelligence(self, di: Any) -> None:
        self._di = di

    async def before_planning(self, ctx: ExecutionContext) -> None:
        if not self._di:
            return
        try:
            desktop_ctx = await self._di.get_full_context()
            summary = desktop_ctx.to_text_summary()
            ctx.metadata["desktop_context"] = summary
            ctx.metadata["desktop_context_windows"] = len(desktop_ctx.windows)
            ctx.metadata["desktop_context_processes"] = len(desktop_ctx.processes)
            logger.debug(
                f"Desktop context injected: {len(desktop_ctx.windows)} windows, "
                f"{len(desktop_ctx.processes)} processes"
            )
        except Exception as e:
            logger.debug(f"Desktop context middleware skipped: {e}")
