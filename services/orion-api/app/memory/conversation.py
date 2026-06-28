from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import time

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: float = Field(default_factory=time.time)

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

    def clear(self) -> None:
        self._sessions.clear()
