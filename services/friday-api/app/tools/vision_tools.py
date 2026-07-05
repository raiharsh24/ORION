from __future__ import annotations
import time
from typing import Any, Optional, TYPE_CHECKING
from loguru import logger
from app.tools.base_tool import BaseTool

if TYPE_CHECKING:
    from app.desktop.controller import DesktopController


class ScreenshotCaptureTool(BaseTool):
    def __init__(self, controller: DesktopController, vision_engine: Any = None) -> None:
        self.controller = controller
        self.vision_engine = vision_engine

    @property
    def name(self) -> str:
        return "vision.screenshot"

    @property
    def description(self) -> str:
        return "Capture a full screenshot of the current screen. Args: None"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        logger.info(f"Executing tool {self.name}")
        result_bytes = await self.controller.take_screenshot(None)
        duration = (time.perf_counter() - start_time) * 1000
        success = len(result_bytes) > 0
        if success:
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=vision")
            return {"success": True, "message": "Screenshot captured.", "size_bytes": len(result_bytes)}
        logger.error(f"Tool {self.name} failed: empty result | duration={duration:.2f}ms | scope=vision")
        return {"success": False, "error": "Failed to capture screenshot."}


class ClipboardImageTool(BaseTool):
    def __init__(self, controller: DesktopController, vision_engine: Any = None) -> None:
        self.controller = controller
        self.vision_engine = vision_engine

    @property
    def name(self) -> str:
        return "vision.clipboard_image"

    @property
    def description(self) -> str:
        return "Read and analyze image content from the system clipboard. Args: None"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        logger.info(f"Executing tool {self.name}")
        clipboard_text = await self.controller.read_clipboard()
        if clipboard_text:
            duration = (time.perf_counter() - start_time) * 1000
            logger.info(f"Tool {self.name} succeeded: clipboard has text content | duration={duration:.2f}ms | scope=vision")
            return {"success": True, "message": "Clipboard contains text, no image found.", "text": clipboard_text}
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"Tool {self.name} completed: clipboard was empty or non-image | duration={duration:.2f}ms | scope=vision")
        return {"success": True, "message": "Clipboard read completed. No image data detected.", "text": ""}


class ImageAnalysisTool(BaseTool):
    def __init__(self, controller: DesktopController, vision_engine: Any = None) -> None:
        self.controller = controller
        self.vision_engine = vision_engine

    @property
    def name(self) -> str:
        return "vision.analyze"

    @property
    def description(self) -> str:
        return "Analyze the current screen or a provided image. Captures a screenshot if no image data is provided. Args: prompt (str, optional)"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        prompt = kwargs.get("prompt", "")
        logger.info(f"Executing tool {self.name} with prompt={prompt[:60] if prompt else ''}")
        if not self.vision_engine:
            duration = (time.perf_counter() - start_time) * 1000
            return {"success": False, "error": "Vision engine not available. Use desktop.screenshot first."}
        image_data = await self.vision_engine.capture_screenshot()
        result = await self.vision_engine.analyze_image(image_data, prompt)
        duration = (time.perf_counter() - start_time) * 1000
        if result.get("success"):
            logger.info(f"Tool {self.name} succeeded | duration={duration:.2f}ms | scope=vision")
        else:
            logger.error(f"Tool {self.name} failed: {result.get('error')} | duration={duration:.2f}ms | scope=vision")
        return result


class OCRTool(BaseTool):
    def __init__(self, controller: DesktopController, vision_engine: Any = None) -> None:
        self.controller = controller
        self.vision_engine = vision_engine

    @property
    def name(self) -> str:
        return "vision.ocr"

    @property
    def description(self) -> str:
        return "Extract text from the current screen using OCR. Captures a screenshot and returns any detected text. Args: None"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        logger.info(f"Executing tool {self.name}")
        if not self.vision_engine:
            duration = (time.perf_counter() - start_time) * 1000
            return {"success": False, "error": "Vision engine not available. Use desktop.screenshot first."}
        image_data = await self.vision_engine.capture_screenshot()
        text = await self.vision_engine.ocr(image_data)
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"Tool {self.name} succeeded: extracted {len(text)} characters | duration={duration:.2f}ms | scope=vision")
        return {"success": True, "text": text, "char_count": len(text)}


class ScreenContextTool(BaseTool):
    def __init__(self, controller: DesktopController, vision_engine: Any = None) -> None:
        self.controller = controller
        self.vision_engine = vision_engine

    @property
    def name(self) -> str:
        return "vision.screen_context"

    @property
    def description(self) -> str:
        return "Capture full screen context: screenshot, OCR text extraction, and UI element detection combined. Args: None"

    async def execute(self, **kwargs) -> Any:
        start_time = time.perf_counter()
        logger.info(f"Executing tool {self.name}")
        if not self.vision_engine:
            duration = (time.perf_counter() - start_time) * 1000
            return {"success": False, "error": "Vision engine not available."}
        image_data = await self.vision_engine.capture_screenshot()
        context = await self.vision_engine.screen_context(image_data, source="tool")
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"Tool {self.name} succeeded: text={context.get('has_text')}, elements={context.get('element_count')} | duration={duration:.2f}ms | scope=vision")
        return {"success": True, "context": context}
