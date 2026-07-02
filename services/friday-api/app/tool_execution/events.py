from typing import Dict, Any, Optional
from app.events.events import FridayEvent


class ToolExecutionStarted(FridayEvent):
    def __init__(self, execution_id: str = "", tool_id: str = "",
                 mode: str = "", total_tools: int = 0) -> None:
        super().__init__(topic="ToolExecutionStarted", data={
            "execution_id": execution_id,
            "tool_id": tool_id,
            "mode": mode,
            "total_tools": total_tools,
        })


class ToolExecutionCompleted(FridayEvent):
    def __init__(self, execution_id: str = "", tool_id: str = "",
                 duration_ms: float = 0.0, output: str = "") -> None:
        super().__init__(topic="ToolExecutionCompleted", data={
            "execution_id": execution_id,
            "tool_id": tool_id,
            "duration_ms": duration_ms,
            "output": str(output) if output else "",
        })


class ToolExecutionFailed(FridayEvent):
    def __init__(self, execution_id: str = "", tool_id: str = "",
                 error: str = "", retries: int = 0) -> None:
        super().__init__(topic="ToolExecutionFailed", data={
            "execution_id": execution_id,
            "tool_id": tool_id,
            "error": error,
            "retries": retries,
        })


class ToolExecutionCancelled(FridayEvent):
    def __init__(self, execution_id: str = "", tool_id: str = "",
                 reason: str = "") -> None:
        super().__init__(topic="ToolExecutionCancelled", data={
            "execution_id": execution_id,
            "tool_id": tool_id,
            "reason": reason,
        })
