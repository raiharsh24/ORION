from typing import Dict, Any
from app.events.events import FridayEvent


class CapabilityRegistered(FridayEvent):
    def __init__(self, capability_id: str, name: str,
                 category: str, version: str) -> None:
        super().__init__(topic="CapabilityRegistered", data={
            "capability_id": capability_id,
            "name": name,
            "category": category,
            "version": version,
        })


class CapabilityRemoved(FridayEvent):
    def __init__(self, capability_id: str, name: str) -> None:
        super().__init__(topic="CapabilityRemoved", data={
            "capability_id": capability_id,
            "name": name,
        })


class CapabilityResolved(FridayEvent):
    def __init__(self, capability_id: str, name: str,
                 resolved_tools: int, duration_ms: float) -> None:
        super().__init__(topic="CapabilityResolved", data={
            "capability_id": capability_id,
            "name": name,
            "resolved_tools": resolved_tools,
            "duration_ms": duration_ms,
        })


class CapabilityHealthChanged(FridayEvent):
    def __init__(self, capability_id: str, name: str,
                 old_status: str, new_status: str) -> None:
        super().__init__(topic="CapabilityHealthChanged", data={
            "capability_id": capability_id,
            "name": name,
            "old_status": old_status,
            "new_status": new_status,
        })


class CapabilityExecuted(FridayEvent):
    def __init__(self, capability_id: str, name: str,
                 success: bool, duration_ms: float,
                 tool_count: int) -> None:
        super().__init__(topic="CapabilityExecuted", data={
            "capability_id": capability_id,
            "name": name,
            "success": success,
            "duration_ms": duration_ms,
            "tool_count": tool_count,
        })
