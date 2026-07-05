from __future__ import annotations
import time
from typing import Any, Optional, TYPE_CHECKING
from loguru import logger
from app.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from app.desktop.controller import DesktopController


class MouseMoveTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.mouse.move"

    @property
    def description(self) -> str:
        return "Move the mouse cursor to absolute screen coordinates. Args: x (int), y (int)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        x = kwargs.get("x")
        y = kwargs.get("y")
        if x is None or y is None:
            return {"success": False, "error": "Missing parameters 'x' and 'y'"}
        result = await self.controller.mouse_move(int(x), int(y))
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"MouseMoveTool: ({x},{y}) -> {result} | {duration:.2f}ms")
        return {"success": result, "x": x, "y": y}


class MouseClickTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.mouse.click"

    @property
    def description(self) -> str:
        return "Click the mouse at the current position. Args: button (str, optional: left/middle/right)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        button = kwargs.get("button", "left")
        result = await self.controller.mouse_click(button)
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"MouseClickTool: {button} -> {result} | {duration:.2f}ms")
        return {"success": result, "button": button}


class MouseDoubleClickTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.mouse.double_click"

    @property
    def description(self) -> str:
        return "Double-click the mouse at the current position."

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        result = await self.controller.mouse_double_click()
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"MouseDoubleClickTool -> {result} | {duration:.2f}ms")
        return {"success": result}


class MouseDragDropTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.mouse.drag_drop"

    @property
    def description(self) -> str:
        return "Drag from one position to another. Args: start_x (int), start_y (int), end_x (int), end_y (int)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        sx = kwargs.get("start_x")
        sy = kwargs.get("start_y")
        ex = kwargs.get("end_x")
        ey = kwargs.get("end_y")
        if any(v is None for v in [sx, sy, ex, ey]):
            return {"success": False, "error": "Missing parameters: start_x, start_y, end_x, end_y"}
        result = await self.controller.mouse_drag_drop(int(sx), int(sy), int(ex), int(ey))
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"MouseDragDropTool: ({sx},{sy})->({ex},{ey}) -> {result} | {duration:.2f}ms")
        return {"success": result}


class KeyboardTypeTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.keyboard.type"

    @property
    def description(self) -> str:
        return "Type text at the current cursor position. Args: text (str)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        text = kwargs.get("text")
        if not text:
            return {"success": False, "error": "Missing parameter 'text'"}
        result = await self.controller.keyboard_type(text)
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"KeyboardTypeTool: {len(text)} chars -> {result} | {duration:.2f}ms")
        return {"success": result, "char_count": len(text)}


class KeyboardShortcutTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.keyboard.shortcut"

    @property
    def description(self) -> str:
        return "Execute a keyboard shortcut. Args: combo (str, e.g. 'ctrl+c')"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        combo = kwargs.get("combo")
        if not combo:
            return {"success": False, "error": "Missing parameter 'combo'"}
        result = await self.controller.keyboard_shortcut(combo)
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"KeyboardShortcutTool: {combo} -> {result} | {duration:.2f}ms")
        return {"success": result, "combo": combo}


class WindowFocusTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.window.focus"

    @property
    def description(self) -> str:
        return "Focus a window by name. Args: window_name (str)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        window_name = kwargs.get("window_name")
        if not window_name:
            return {"success": False, "error": "Missing parameter 'window_name'"}
        result = await self.controller.window_focus(window_name)
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"WindowFocusTool: {window_name} -> {result} | {duration:.2f}ms")
        return {"success": result.get("success", False), **result}


class CaptureWindowTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.screenshot.window"

    @property
    def description(self) -> str:
        return "Capture a screenshot of the active window only."

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        result_bytes = await self.controller.screenshot_handler.capture_active_window()
        duration = (time.perf_counter() - start_time) * 1000
        success = len(result_bytes) > 0
        logger.info(f"CaptureWindowTool -> {len(result_bytes)} bytes | {duration:.2f}ms")
        return {"success": success, "size_bytes": len(result_bytes)}


class CaptureRegionTool(BaseTool):
    def __init__(self, controller: DesktopController) -> None:
        self.controller = controller

    @property
    def name(self) -> str:
        return "desktop.screenshot.region"

    @property
    def description(self) -> str:
        return "Capture a region of the screen. Args: x (int), y (int), width (int), height (int)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        x = kwargs.get("x", 0)
        y = kwargs.get("y", 0)
        w = kwargs.get("width", 100)
        h = kwargs.get("height", 100)
        result_bytes = await self.controller.screenshot_handler.capture_region(int(x), int(y), int(w), int(h))
        duration = (time.perf_counter() - start_time) * 1000
        success = len(result_bytes) > 0
        logger.info(f"CaptureRegionTool: ({x},{y},{w}x{h}) -> {len(result_bytes)} bytes | {duration:.2f}ms")
        return {"success": success, "size_bytes": len(result_bytes)}
