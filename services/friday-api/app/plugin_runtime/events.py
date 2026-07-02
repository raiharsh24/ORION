from typing import Dict, Any
from app.events.events import FridayEvent


class PluginDiscovered(FridayEvent):
    def __init__(self, plugin_id: str, name: str, path: str) -> None:
        super().__init__(topic="PluginDiscovered", data={
            "plugin_id": plugin_id, "name": name, "path": path,
        })


class PluginValidated(FridayEvent):
    def __init__(self, plugin_id: str, name: str, valid: bool,
                 errors: list) -> None:
        super().__init__(topic="PluginValidated", data={
            "plugin_id": plugin_id, "name": name,
            "valid": valid, "errors": errors,
        })


class PluginLoaded(FridayEvent):
    def __init__(self, plugin_id: str, name: str, version: str,
                 load_time_ms: float) -> None:
        super().__init__(topic="PluginLoaded", data={
            "plugin_id": plugin_id, "name": name,
            "version": version, "load_time_ms": load_time_ms,
        })


class PluginInitialized(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 init_time_ms: float) -> None:
        super().__init__(topic="PluginInitialized", data={
            "plugin_id": plugin_id, "name": name,
            "init_time_ms": init_time_ms,
        })


class PluginReady(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 tool_count: int = 0, cap_count: int = 0) -> None:
        super().__init__(topic="PluginReady", data={
            "plugin_id": plugin_id, "name": name,
            "tool_count": tool_count, "cap_count": cap_count,
        })


class PluginReloaded(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 reload_count: int, reload_time_ms: float) -> None:
        super().__init__(topic="PluginReloaded", data={
            "plugin_id": plugin_id, "name": name,
            "reload_count": reload_count,
            "reload_time_ms": reload_time_ms,
        })


class PluginSuspended(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 reason: str = "") -> None:
        super().__init__(topic="PluginSuspended", data={
            "plugin_id": plugin_id, "name": name, "reason": reason,
        })


class PluginResumed(FridayEvent):
    def __init__(self, plugin_id: str, name: str) -> None:
        super().__init__(topic="PluginResumed", data={
            "plugin_id": plugin_id, "name": name,
        })


class PluginUnloaded(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 cleanup_time_ms: float = 0.0) -> None:
        super().__init__(topic="PluginUnloaded", data={
            "plugin_id": plugin_id, "name": name,
            "cleanup_time_ms": cleanup_time_ms,
        })


class PluginFailed(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 error: str, stage: str = "") -> None:
        super().__init__(topic="PluginFailed", data={
            "plugin_id": plugin_id, "name": name,
            "error": error, "stage": stage,
        })


class PluginSandboxViolation(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 violation_type: str, detail: str) -> None:
        super().__init__(topic="PluginSandboxViolation", data={
            "plugin_id": plugin_id, "name": name,
            "violation_type": violation_type, "detail": detail,
        })


class PluginResourceWarning(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 resource: str, usage: float, limit: float) -> None:
        super().__init__(topic="PluginResourceWarning", data={
            "plugin_id": plugin_id, "name": name,
            "resource": resource, "usage": usage, "limit": limit,
        })
