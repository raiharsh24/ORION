from typing import Optional, Any, List
from datetime import datetime, timezone
from loguru import logger

from app.desktop_intelligence.context import (
    DesktopContext,
    WindowInfo,
    ClipboardState,
    ProcessInfo,
    ScreenInfo,
)


class DesktopIntelligence:
    def __init__(
        self,
        desktop_controller: Any,
        vision_engine: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._desktop = desktop_controller
        self._vision = vision_engine
        self._event_bus = event_bus
        self._last_context: Optional[DesktopContext] = None

    async def get_window_context(self) -> List[WindowInfo]:
        windows = []
        try:
            result = await self._desktop.window_manager.list_windows()
            if result.get("success"):
                for w in result.get("windows", []):
                    windows.append(
                        WindowInfo(
                            id=w.get("id", ""),
                            title=w.get("name", ""),
                            is_focused=w.get("focused", False),
                        )
                    )
        except Exception as e:
            logger.debug(f"Window context failed: {e}")
        return windows

    async def get_clipboard_context(self) -> ClipboardState:
        text = ""
        try:
            text = await self._desktop.read_clipboard()
        except Exception as e:
            logger.debug(f"Clipboard context failed: {e}")
        return ClipboardState(
            text=text or "",
            has_image=False,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    async def get_process_context(self) -> List[ProcessInfo]:
        processes = []
        try:
            procs = await self._desktop.list_running_processes()
            for p in procs:
                processes.append(
                    ProcessInfo(
                        pid=p.get("pid", 0),
                        name=p.get("name", "unknown"),
                        status=p.get("status", "unknown"),
                    )
                )
        except Exception as e:
            logger.debug(f"Process context failed: {e}")
        return processes

    async def get_screen_context(self) -> ScreenInfo:
        info = ScreenInfo()
        try:
            if self._vision:
                ctx = await self._vision.get_screen_context()
                if ctx:
                    info.ocr_text = ctx.get("ocr_text", "")
                    info.ui_element_count = ctx.get("element_count", 0)
                    info.screenshot_available = bool(ctx.get("has_screenshot", False))
            img = await self._desktop.take_screenshot()
            if img and len(img) > 100:
                info.screenshot_available = True
        except Exception as e:
            logger.debug(f"Screen context failed: {e}")
        return info

    async def get_full_context(self) -> DesktopContext:
        windows = await self.get_window_context()
        clipboard = await self.get_clipboard_context()
        processes = await self.get_process_context()
        screen = await self.get_screen_context()

        active_title = ""
        active_id = ""
        for w in windows:
            if w.is_focused:
                active_title = w.title
                active_id = w.id
                break

        ctx = DesktopContext(
            timestamp=datetime.now(timezone.utc).isoformat(),
            windows=windows,
            clipboard=clipboard,
            processes=processes,
            screen=screen,
            active_window_title=active_title,
            active_window_id=active_id,
        )
        self._last_context = ctx
        return ctx

    async def get_text_summary(self) -> str:
        ctx = await self.get_full_context()
        return ctx.to_text_summary()

    def get_last_context(self) -> Optional[DesktopContext]:
        return self._last_context

    def health(self) -> dict:
        return {
            "status": "healthy",
            "vision_available": self._vision is not None,
            "last_context": self._last_context.timestamp if self._last_context else None,
        }
