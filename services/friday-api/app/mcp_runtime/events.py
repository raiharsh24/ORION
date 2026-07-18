from typing import Dict, Any

from app.events.events import FridayEvent


class MCPServerConnected(FridayEvent):
    def __init__(self, server_name: str, version: str, tools_count: int) -> None:
        super().__init__(topic="MCPServerConnected", data={
            "server_name": server_name,
            "version": version,
            "tools_count": tools_count,
        })


class MCPServerDisconnected(FridayEvent):
    def __init__(self, server_name: str, error: str = "") -> None:
        super().__init__(topic="MCPServerDisconnected", data={
            "server_name": server_name,
            "error": error,
        })


class MCPToolDiscovered(FridayEvent):
    def __init__(self, server_name: str, tool_name: str) -> None:
        super().__init__(topic="MCPToolDiscovered", data={
            "server_name": server_name,
            "tool_name": tool_name,
        })


class MCPToolCallCompleted(FridayEvent):
    def __init__(self, server_name: str, tool_name: str, success: bool, duration_ms: float) -> None:
        super().__init__(topic="MCPToolCallCompleted", data={
            "server_name": server_name,
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
        })
