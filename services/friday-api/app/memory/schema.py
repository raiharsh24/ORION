from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import time
import uuid

class ChatMessage(BaseModel):
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: float = Field(default_factory=time.time)

class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    category: str = "general"  # "preference", "decision", "milestone", "chat", "general"
    importance: int = Field(default=5, ge=1, le=10)  # score 1-10
    timestamp: float = Field(default_factory=time.time)
    expiration: Optional[float] = None  # optional expiration epoch timestamp
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WorkingMemory(BaseModel):
    recent_messages: List[ChatMessage] = Field(default_factory=list)
    active_tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    temporary_reasoning_state: Dict[str, Any] = Field(default_factory=dict)

class SessionMemory(BaseModel):
    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    summary: Optional[str] = "Conversation session initialized."
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    context: Optional[str] = "nominal"
    tool_used: Optional[str] = None
    tool_output: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UserMemory(BaseModel):
    user_id: str = "default_user"
    preferences: Dict[str, Any] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)

class ProjectMemory(BaseModel):
    project_id: str
    name: str
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    milestones: Dict[str, Any] = Field(default_factory=dict)
    todos: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)
