from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import time

from app.memory.schema import ChatMessage

class ChatSession(BaseModel):
    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    summary: Optional[str] = "Conversation session initialized."
    context: Optional[str] = "nominal"
    tool_used: Optional[str] = None
    tool_output: Optional[str] = None

class ConversationMemory:
    """
    Manages active chat sessions, summaries, and semantic contexts.
    """
    def __init__(self) -> None:
        self._sessions: Dict[str, ChatSession] = {}

    def get_or_create_session(self, session_id: str) -> ChatSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatSession(session_id=session_id)
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_or_create_session(session_id)
        session.messages.append(ChatMessage(role=role, content=content))

    def get_history_string(self, session_id: str) -> str:
        session = self.get_or_create_session(session_id)
        return "\n".join([f"{msg.role.capitalize()}: {msg.content}" for msg in session.messages])

    def update_summary(self, session_id: str, summary: str) -> None:
        session = self.get_or_create_session(session_id)
        session.summary = summary

    def update_context(self, session_id: str, context: str) -> None:
        session = self.get_or_create_session(session_id)
        session.context = context

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[ChatSession]:
        return list(self._sessions.values())

    def prune_sessions(self, max_age_seconds: int = 86400,
                       max_messages: int = 200) -> int:
        """Remove sessions older than max_age_seconds and trim message lists."""
        now = time.time()
        pruned = 0
        for sid in list(self._sessions.keys()):
            session = self._sessions[sid]
            if now - session.created_at > max_age_seconds:
                del self._sessions[sid]
                pruned += 1
            elif len(session.messages) > max_messages:
                session.messages = session.messages[-max_messages:]
                pruned += 1
        return pruned

    def clear(self) -> None:
        self._sessions.clear()
