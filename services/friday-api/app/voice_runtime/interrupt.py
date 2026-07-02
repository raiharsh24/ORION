from typing import Optional, Dict, Any, Callable, List
from app.voice_runtime.base import VoicePipelineStage


class InterruptHandler:
    def __init__(self, runtime: Any = None):
        self._runtime = runtime
        self._mission_pause_map: Dict[str, str] = {}
        self._on_interrupt: List[Callable] = []
        self._on_resume: List[Callable] = []

    def on_interrupt(self, callback: Callable) -> None:
        self._on_interrupt.append(callback)

    def on_resume(self, callback: Callable) -> None:
        self._on_resume.append(callback)

    async def handle_user_interrupt(self, session_id: str) -> bool:
        for cb in self._on_interrupt:
            try:
                cb(session_id, "user")
            except Exception:
                pass

        mission_id = self._mission_pause_map.get(session_id)
        if mission_id and self._runtime:
            try:
                if hasattr(self._runtime, "pause"):
                    await self._runtime.pause(mission_id)
                    return True
            except Exception:
                pass
        return False

    async def handle_assistant_interrupt(self, session_id: str) -> bool:
        for cb in self._on_interrupt:
            try:
                cb(session_id, "assistant")
            except Exception:
                pass
        return True

    async def cancel_speaking(self, session_id: str,
                                speech_manager: Any) -> bool:
        if speech_manager and hasattr(speech_manager, "cancel_synthesis"):
            speech_manager.cancel_synthesis()
            return True
        return False

    async def cancel_mission(self, session_id: str) -> bool:
        mission_id = self._mission_pause_map.get(session_id)
        if mission_id and self._runtime:
            try:
                if hasattr(self._runtime, "cancel"):
                    await self._runtime.cancel(mission_id)
                    self._mission_pause_map.pop(session_id, None)
                    return True
            except Exception:
                pass
        return False

    async def resume_mission(self, session_id: str) -> bool:
        mission_id = self._mission_pause_map.get(session_id)
        if mission_id and self._runtime:
            try:
                if hasattr(self._runtime, "resume"):
                    result = await self._runtime.resume(mission_id)
                    if result:
                        self._mission_pause_map.pop(session_id, None)
                        for cb in self._on_resume:
                            try:
                                cb(session_id, mission_id)
                            except Exception:
                                pass
                        return True
            except Exception:
                pass
        return False

    def track_mission(self, session_id: str, mission_id: str) -> None:
        self._mission_pause_map[session_id] = mission_id

    def untrack_mission(self, session_id: str) -> None:
        self._mission_pause_map.pop(session_id, None)

    @property
    def tracked_mission_count(self) -> int:
        return len(self._mission_pause_map)
