from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time


@dataclass
class ExecutionSnapshot:
    execution_id: str
    goal: str
    intent: str
    selected_tools: List[Dict[str, Any]]
    confidence: float
    execution_duration_ms: float
    success: bool
    fallback_used: bool
    errors: List[str]
    completed_tasks: List[Dict[str, Any]]
    session_id: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "goal": self.goal,
            "intent": self.intent,
            "selected_tools": self.selected_tools,
            "confidence": self.confidence,
            "execution_duration_ms": self.execution_duration_ms,
            "success": self.success,
            "fallback_used": self.fallback_used,
            "errors": self.errors,
            "completed_tasks": self.completed_tasks,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ReflectionReport:
    execution_id: str
    snapshot: ExecutionSnapshot
    what_succeeded: List[str]
    what_failed: List[str]
    why: str
    possible_improvements: List[str]
    recommended_tool_ordering: List[str]
    execution_quality_score: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "snapshot": self.snapshot.to_dict(),
            "what_succeeded": self.what_succeeded,
            "what_failed": self.what_failed,
            "why": self.why,
            "possible_improvements": self.possible_improvements,
            "recommended_tool_ordering": self.recommended_tool_ordering,
            "execution_quality_score": self.execution_quality_score,
            "timestamp": self.timestamp,
        }
