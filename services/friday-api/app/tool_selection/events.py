from typing import Dict, Any, Optional, List
from app.events.events import FridayEvent


class ToolSelectionStarted(FridayEvent):
    def __init__(self, intent: str = "", context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(topic="ToolSelectionStarted", data={
            "intent": intent,
            "context": context or {},
        })


class ToolSelected(FridayEvent):
    def __init__(self, tool_id: str = "", name: str = "",
                 score: float = 0.0, reason: str = "") -> None:
        super().__init__(topic="ToolSelected", data={
            "tool_id": tool_id,
            "name": name,
            "score": score,
            "reason": reason,
        })


class FallbackToolSelected(FridayEvent):
    def __init__(self, tool_id: str = "", name: str = "",
                 original_tool_id: str = "", reason: str = "") -> None:
        super().__init__(topic="FallbackToolSelected", data={
            "tool_id": tool_id,
            "name": name,
            "original_tool_id": original_tool_id,
            "reason": reason,
        })


class ToolSelectionCompleted(FridayEvent):
    def __init__(self, intent: str = "", selected_count: int = 0,
                 fallback_count: int = 0, confidence: float = 0.0,
                 latency_ms: float = 0.0) -> None:
        super().__init__(topic="ToolSelectionCompleted", data={
            "intent": intent,
            "selected_count": selected_count,
            "fallback_count": fallback_count,
            "confidence": confidence,
            "latency_ms": latency_ms,
        })
