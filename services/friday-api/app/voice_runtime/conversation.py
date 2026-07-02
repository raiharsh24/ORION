import time
import uuid
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime, timezone

from app.voice_runtime.base import (
    VoiceSession, VoiceMessage, VoicePipelineStage, VoiceConfig,
)


class ConversationManager:
    def __init__(self, config: Optional[VoiceConfig] = None,
                 memory_engine: Any = None):
        self._config = config or VoiceConfig()
        self._sessions: Dict[str, VoiceSession] = {}
        self._memory_engine = memory_engine
        self._on_session_start: List[Callable] = []
        self._on_session_end: List[Callable] = []
        self._on_message: List[Callable] = []

    def on_session_start(self, callback: Callable) -> None:
        self._on_session_start.append(callback)

    def on_session_end(self, callback: Callable) -> None:
        self._on_session_end.append(callback)

    def on_message(self, callback: Callable) -> None:
        self._on_message.append(callback)

    def create_session(self, session_id: Optional[str] = None,
                        user_id: str = "default") -> VoiceSession:
        sid = session_id or str(uuid.uuid4())
        session = VoiceSession(
            session_id=sid,
            user_id=user_id,
            pipeline_stage=VoicePipelineStage.IDLE,
        )
        self._sessions[sid] = session
        for cb in self._on_session_start:
            try:
                cb(session)
            except Exception:
                pass
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.is_active = False
        session.pipeline_stage = VoicePipelineStage.IDLE
        for cb in self._on_session_end:
            try:
                cb(session)
            except Exception:
                pass
        return True

    def add_message(self, session_id: str, role: str, content: str,
                     duration_ms: float = 0.0) -> Optional[VoiceMessage]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        msg = session.add_message(role, content, duration_ms)
        if len(session.messages) > self._config.max_conversation_turns * 2:
            session.messages = session.messages[-(self._config.max_conversation_turns * 2):]

        if self._memory_engine and hasattr(self._memory_engine, "retrieve_relevant_context"):
            try:
                self._memory_engine.retrieve_relevant_context(
                    query=content,
                    session_id=session_id,
                    user_id=session.user_id,
                    limit=3,
                )
            except Exception:
                pass

        for cb in self._on_message:
            try:
                cb(session, msg)
            except Exception:
                pass
        return msg

    def set_pipeline_stage(self, session_id: str,
                            stage: VoicePipelineStage) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.pipeline_stage = stage
        session.updated_at = datetime.now(timezone.utc)
        return True

    def set_mission(self, session_id: str,
                     mission_id: Optional[str]) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.active_mission_id = mission_id
        session.updated_at = datetime.now(timezone.utc)
        return True

    def list_sessions(self) -> List[VoiceSession]:
        return list(self._sessions.values())

    def list_active_sessions(self) -> List[VoiceSession]:
        return [s for s in self._sessions.values() if s.is_active]

    def end_inactive_sessions(self, max_age_minutes: float = 30.0) -> int:
        now = datetime.now(timezone.utc)
        ended = 0
        for sid, session in dict(self._sessions).items():
            age = (now - session.updated_at).total_seconds() / 60
            if age > max_age_minutes and session.is_active:
                self.end_session(sid)
                ended += 1
        return ended

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_session_count(self) -> int:
        return len(self.list_active_sessions())
