from typing import Dict, Any, List, Optional
from loguru import logger

from app.vision.router import VisionRouter
from app.vision.provider import VisionProvider
from app.vision.context import ScreenContextBuilder
from app.vision.events import (
    VisionCaptureStarted,
    VisionCaptureCompleted,
    VisionAnalysisStarted,
    VisionAnalysisCompleted,
    VisionProviderError,
)


class VisionEngine:
    def __init__(self, event_bus: Any = None, desktop_controller: Any = None) -> None:
        self._event_bus = event_bus
        self._desktop = desktop_controller
        self._router = VisionRouter()
        self._context_builder: Optional[ScreenContextBuilder] = None
        self._initialized = False

    @property
    def router(self) -> VisionRouter:
        return self._router

    @property
    def context_builder(self) -> Optional[ScreenContextBuilder]:
        return self._context_builder

    async def initialize(self) -> None:
        if self._initialized:
            return
        default_provider = VisionProvider()
        self._router.register_provider(default_provider.name, default_provider, is_default=True)
        self._context_builder = ScreenContextBuilder(self._router, self._event_bus)
        self._initialized = True
        logger.info("VisionEngine initialized with default provider")

    async def start(self) -> None:
        logger.info("VisionEngine service started")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("VisionEngine service shut down")

    def health(self) -> Dict[str, Any]:
        if not self._initialized:
            return {"status": "WARNING", "message": "VisionEngine not initialized"}
        return {
            "status": "HEALTHY",
            "message": "VisionEngine operational",
            "details": {
                "providers": self._router.list_providers(),
                "default_provider": self._router._default,
            },
        }

    async def capture_screenshot(self) -> bytes:
        self._publish(VisionCaptureStarted("screenshot"))
        if self._desktop and hasattr(self._desktop, "take_screenshot"):
            image_data = await self._desktop.take_screenshot()
        else:
            image_data = self._fallback_screenshot()
        self._publish(VisionCaptureCompleted("screenshot", len(image_data), "png"))
        return image_data

    def _fallback_screenshot(self) -> bytes:
        import struct
        png_header = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', 0)
        idat_data = b'x\x9c\x62\x60\x60\x00\x00\x00\x00\x01\x00\x01'
        import zlib
        compressed = zlib.compress(idat_data)
        idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', 0)
        iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', 0)
        return png_header + ihdr_chunk + idat_chunk + iend_chunk

    async def analyze_image(self, image_data: bytes, prompt: Optional[str] = None, provider_name: Optional[str] = None) -> Dict[str, Any]:
        self._publish(VisionAnalysisStarted("image"))
        try:
            result = await self._router.analyze_image(image_data, prompt, provider_name)
            self._publish(VisionAnalysisCompleted("image", result.get("description", ""), result.get("confidence", 1.0)))
            return result
        except Exception as e:
            logger.error(f"VisionEngine.analyze_image failed: {e}")
            self._publish(VisionProviderError(provider_name or "default", str(e)))
            return {"success": False, "error": str(e)}

    async def ocr(self, image_data: bytes, provider_name: Optional[str] = None) -> str:
        return await self._router.ocr(image_data, provider_name)

    async def detect_ui_elements(self, image_data: bytes, provider_name: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self._router.detect_ui_elements(image_data, provider_name)

    async def screen_context(
        self,
        image_data: bytes,
        source: str = "screenshot",
        session_id: Optional[str] = None,
        memory_engine: Any = None,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._context_builder:
            return {"source": source, "ocr_text": "", "has_text": False, "ui_elements": [], "element_count": 0}
        return await self._context_builder.build_context(
            image_data, source, session_id, memory_engine, provider_name,
        )

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                self._event_bus.publish_background(event)
            except Exception as e:
                logger.debug(f"VisionEngine: event publish failed: {e}")
