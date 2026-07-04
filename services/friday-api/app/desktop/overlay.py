import asyncio
import json
import os
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger


class DesktopOverlayService:
    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        self._active: bool = False
        self._state: Dict[str, Any] = {
            "detected_elements": [],
            "mouse_position": (0, 0),
            "active_mission": None,
            "current_action": None,
            "confidence": 0.0,
            "selected_target": None,
            "overlay_text": "",
        }
        self._state_file: Optional[str] = None
        self._publish_task: Optional[asyncio.Task] = None

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def state(self) -> Dict[str, Any]:
        return dict(self._state)

    async def start(self, publish_interval: float = 0.5) -> None:
        if self._active:
            return
        self._active = True
        self._state_file = os.path.join(tempfile.gettempdir(), "friday_overlay_state.json")
        if self._event_bus:
            self._publish_task = asyncio.create_task(
                self._publish_loop(publish_interval)
            )
        self._write_state()
        logger.info("DesktopOverlayService started")

    async def stop(self) -> None:
        self._active = False
        if self._publish_task:
            self._publish_task.cancel()
            try:
                await self._publish_task
            except asyncio.CancelledError:
                pass
            self._publish_task = None
        self._cleanup_state_file()
        logger.info("DesktopOverlayService stopped")

    def update_detected_elements(self, elements: List[Dict[str, Any]]) -> None:
        self._state["detected_elements"] = elements
        self._write_state()

    def update_mouse_position(self, x: int, y: int) -> None:
        self._state["mouse_position"] = (x, y)
        self._write_state()

    def update_active_mission(self, mission_id: Optional[str], action: Optional[str] = None) -> None:
        self._state["active_mission"] = mission_id
        if action:
            self._state["current_action"] = action
        self._write_state()

    def update_confidence(self, confidence: float) -> None:
        self._state["confidence"] = confidence
        self._write_state()

    def update_selected_target(self, target: Optional[Dict[str, Any]]) -> None:
        self._state["selected_target"] = target
        self._write_state()

    def update_overlay_text(self, text: str) -> None:
        self._state["overlay_text"] = text
        self._write_state()

    def _write_state(self) -> None:
        if not self._state_file:
            return
        try:
            with open(self._state_file, "w") as f:
                json.dump(self._serialize_state(), f)
        except Exception as e:
            logger.debug(f"Failed to write overlay state: {e}")

    def _cleanup_state_file(self) -> None:
        if self._state_file and os.path.exists(self._state_file):
            try:
                os.remove(self._state_file)
            except Exception:
                pass

    async def _publish_loop(self, interval: float) -> None:
        while self._active:
            if self._event_bus:
                try:
                    state = self._serialize_state()
                    from app.desktop.events import DesktopOverlayUpdated
                    await self._event_bus.publish(DesktopOverlayUpdated(state))
                except Exception as e:
                    logger.debug(f"Overlay publish error: {e}")
            await asyncio.sleep(interval)

    def _serialize_state(self) -> Dict[str, Any]:
        s = self._state
        return {
            "element_count": len(s["detected_elements"]),
            "mouse_x": s["mouse_position"][0],
            "mouse_y": s["mouse_position"][1],
            "active_mission": s["active_mission"],
            "current_action": s["current_action"],
            "confidence": s["confidence"],
            "selected_target": s["selected_target"],
            "overlay_text": s["overlay_text"],
        }

    def read_state(self) -> Optional[Dict[str, Any]]:
        if not self._state_file or not os.path.exists(self._state_file):
            return None
        try:
            with open(self._state_file, "r") as f:
                return json.load(f)
        except Exception:
            return None
