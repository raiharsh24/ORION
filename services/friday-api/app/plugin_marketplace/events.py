from typing import Dict, Any, List
from app.events.events import FridayEvent


class PluginInstalled(FridayEvent):
    def __init__(self, plugin_id: str, name: str, version: str) -> None:
        super().__init__(topic="PluginInstalled", data={
            "plugin_id": plugin_id, "name": name, "version": version,
        })


class PluginUpdated(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 old_version: str, new_version: str) -> None:
        super().__init__(topic="PluginUpdated", data={
            "plugin_id": plugin_id, "name": name,
            "old_version": old_version, "new_version": new_version,
        })


class PluginRemoved(FridayEvent):
    def __init__(self, plugin_id: str, name: str, version: str) -> None:
        super().__init__(topic="PluginRemoved", data={
            "plugin_id": plugin_id, "name": name, "version": version,
        })


class PluginRollback(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 from_version: str, to_version: str) -> None:
        super().__init__(topic="PluginRollback", data={
            "plugin_id": plugin_id, "name": name,
            "from_version": from_version, "to_version": to_version,
        })


class RepositoryUpdated(FridayEvent):
    def __init__(self, repository: str,
                 added: int, removed: int, total: int) -> None:
        super().__init__(topic="RepositoryUpdated", data={
            "repository": repository,
            "added": added, "removed": removed, "total": total,
        })


class DependencyResolved(FridayEvent):
    def __init__(self, plugin_id: str, dependencies: List[str],
                 success: bool) -> None:
        super().__init__(topic="DependencyResolved", data={
            "plugin_id": plugin_id,
            "dependencies": dependencies, "success": success,
        })


class PackageDownloaded(FridayEvent):
    def __init__(self, plugin_id: str, name: str,
                 version: str, size_bytes: int) -> None:
        super().__init__(topic="PackageDownloaded", data={
            "plugin_id": plugin_id, "name": name,
            "version": version, "size_bytes": size_bytes,
        })


class PackageVerified(FridayEvent):
    def __init__(self, plugin_id: str, version: str,
                 valid: bool, errors: List[str]) -> None:
        super().__init__(topic="PackageVerified", data={
            "plugin_id": plugin_id, "version": version,
            "valid": valid, "errors": errors,
        })
