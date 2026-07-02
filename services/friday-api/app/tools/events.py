from typing import Dict, Any, Optional
from app.events.events import FridayEvent


class ToolRegistered(FridayEvent):
    def __init__(self, tool_id: str = "", name: str = "",
                 category: str = "", version: str = "",
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(topic="ToolRegistered", data={
            "tool_id": tool_id,
            "name": name,
            "category": category,
            "version": version,
            "metadata": metadata or {},
        })


class ToolRemoved(FridayEvent):
    def __init__(self, tool_id: str = "", name: str = "",
                 reason: str = "") -> None:
        super().__init__(topic="ToolRemoved", data={
            "tool_id": tool_id,
            "name": name,
            "reason": reason,
        })


class ToolHealthChanged(FridayEvent):
    def __init__(self, tool_id: str = "", name: str = "",
                 status: str = "", message: str = "") -> None:
        super().__init__(topic="ToolHealthChanged", data={
            "tool_id": tool_id,
            "name": name,
            "status": status,
            "message": message,
        })
