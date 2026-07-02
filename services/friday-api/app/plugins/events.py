from typing import Dict, Any
from app.events.events import FridayEvent


class PluginInstalled(FridayEvent):
    def __init__(self, plugin_id: str, name: str, version: str) -> None:
        super().__init__(topic="PluginInstalled", data={
            "plugin_id": plugin_id, "name": name, "version": version,
        })


class PluginLoaded(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 load_time_ms: float) -> None:
        super().__init__(topic="PluginLoaded", data={
            "plugin_id": plugin_id, "name": name, "load_time_ms": load_time_ms,
        })


class PluginEnabled(FridayEvent):
    def __init__(self, plugin_id: str, name: str) -> None:
        super().__init__(topic="PluginEnabled", data={
            "plugin_id": plugin_id, "name": name,
        })


class PluginDisabled(FridayEvent):
    def __init__(self, plugin_id: str, name: str) -> None:
        super().__init__(topic="PluginDisabled", data={
            "plugin_id": plugin_id, "name": name,
        })


class PluginUnloaded(FridayEvent):
    def __init__(self, plugin_id: str, name: str) -> None:
        super().__init__(topic="PluginUnloaded", data={
            "plugin_id": plugin_id, "name": name,
        })


class PluginRemoved(FridayEvent):
    def __init__(self, plugin_id: str, name: str) -> None:
        super().__init__(topic="PluginRemoved", data={
            "plugin_id": plugin_id, "name": name,
        })


class PluginFailed(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 error: str) -> None:
        super().__init__(topic="PluginFailed", data={
            "plugin_id": plugin_id, "name": name, "error": error,
        })
