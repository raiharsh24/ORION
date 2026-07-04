import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.vision.router import VisionRouter
from app.vision.events import (
    VisionOCRExtracted,
    VisionUIElementsDetected,
    VisionContextBuilt,
    VisionMemoryStored,
)


class ScreenContextBuilder:
    def __init__(self, vision_router: VisionRouter, event_bus: Any = None) -> None:
        self._vision_router = vision_router
        self._event_bus = event_bus

    async def build_context(
        self,
        image_data: bytes,
        source: str = "screenshot",
        session_id: Optional[str] = None,
        memory_engine: Any = None,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        start = time.perf_counter()

        ocr_text = await self._vision_router.ocr(image_data, provider_name=provider_name)
        self._publish(VisionOCRExtracted(source, len(ocr_text)))

        ui_elements = await self._vision_router.detect_ui_elements(image_data, provider_name=provider_name)
        self._publish(VisionUIElementsDetected(source, len(ui_elements)))

        has_text = bool(ocr_text.strip()) and "[OCR unavailable" not in ocr_text

        context = {
            "source": source,
            "ocr_text": ocr_text,
            "has_text": has_text,
            "ui_elements": ui_elements,
            "element_count": len(ui_elements),
            "captured_at": time.time(),
        }

        self._publish(VisionContextBuilt(source, has_text, len(ui_elements)))

        if session_id and memory_engine:
            session = memory_engine.get_or_create_session(session_id)
            session.context = session.context or {}
            if isinstance(session.context, dict):
                stored = {
                    "type": "vision_context",
                    "source": source,
                    "ocr_text": ocr_text,
                    "has_text": has_text,
                    "element_count": len(ui_elements),
                    "captured_at": context["captured_at"],
                }
                session.context["last_vision"] = stored
                memory_engine.save_session(session)
                self._publish(VisionMemoryStored(session_id, source))
                logger.info(f"ScreenContextBuilder: stored vision context for session {session_id}")

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(f"ScreenContextBuilder: built context in {duration_ms:.1f}ms (text={has_text}, elements={len(ui_elements)})")
        return context

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                self._event_bus.publish_background(event)
            except Exception as e:
                logger.debug(f"ScreenContextBuilder: event publish failed: {e}")
