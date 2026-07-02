from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone
from loguru import logger

from app.plugins.base import (
    Plugin, PluginState, PluginMetadata, PluginManifest,
    PluginDependency, PluginHealth, PluginPermission,
)
from app.plugins.events import (
    PluginInstalled, PluginRemoved, PluginEnabled,
    PluginDisabled, PluginFailed,
)
from app.plugins.health import PluginEngineHealth


class PluginRegistry:
    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._plugins: Dict[str, Plugin] = {}
        self._health: Dict[str, PluginHealth] = {}

    def install(self, manifest: PluginManifest) -> Optional[Plugin]:
        if manifest.id in self._plugins:
            logger.warning(f"Plugin '{manifest.id}' already registered")
            return None
        plugin = Plugin(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            author=manifest.author,
            description=manifest.description,
            state=PluginState.INSTALLED,
            dependencies=list(manifest.dependencies),
            required_capabilities=list(manifest.required_capabilities),
            permissions=list(manifest.permissions),
            metadata=dict(manifest.metadata),
        )
        self._plugins[manifest.id] = plugin
        self._health[manifest.id] = PluginHealth(
            status="installed", loaded=False, enabled=False,
        )
        self._publish(PluginInstalled(
            plugin_id=plugin.id, name=plugin.name, version=plugin.version,
        ))
        return plugin

    def remove(self, plugin_id: str) -> bool:
        plugin = self._plugins.pop(plugin_id, None)
        if plugin is None:
            return False
        self._health.pop(plugin_id, None)
        self._publish(PluginRemoved(
            plugin_id=plugin_id, name=plugin.name,
        ))
        return True

    def get(self, plugin_id: str) -> Optional[Plugin]:
        return self._plugins.get(plugin_id)

    def get_health(self, plugin_id: str) -> Optional[PluginHealth]:
        return self._health.get(plugin_id)

    def update_state(self, plugin_id: str, state: PluginState,
                     error: Optional[str] = None) -> Optional[Plugin]:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return None
        plugin.state = state
        plugin.updated_at = datetime.now(timezone.utc)
        health = self._health.get(plugin_id)
        if health is not None:
            if state == PluginState.ENABLED:
                health.enabled = True
                health.last_enabled = datetime.now(timezone.utc)
            elif state == PluginState.DISABLED:
                health.enabled = False
            elif state == PluginState.LOADED:
                health.loaded = True
                health.last_loaded = datetime.now(timezone.utc)
            elif state == PluginState.FAILED:
                health.last_error = error
                health.crash_count += 1
                health.status = "failed"
            elif state == PluginState.UNLOADED:
                health.loaded = False
                health.enabled = False
        return plugin

    def update_health(self, plugin_id: str, load_time_ms: float = 0.0) -> None:
        health = self._health.get(plugin_id)
        if health is None:
            return
        health.load_time_ms = load_time_ms

    def list_plugins(self) -> List[Plugin]:
        return list(self._plugins.values())

    def list_metadata(self) -> List[PluginMetadata]:
        result = []
        for p in self._plugins.values():
            h = self._health.get(p.id)
            result.append(PluginMetadata(
                id=p.id, name=p.name, version=p.version,
                author=p.author, description=p.description,
                state=p.state,
                dependency_count=len(p.dependencies),
                permission_count=len(p.permissions),
                is_enabled=p.is_enabled,
                installed_at=p.installed_at,
            ))
        return result

    def list_by_state(self, state: PluginState) -> List[Plugin]:
        return [p for p in self._plugins.values() if p.state == state]

    def search(self, query: str) -> List[Plugin]:
        q = query.lower()
        results = []
        for p in self._plugins.values():
            if q in p.id.lower() or q in p.name.lower() or q in p.description.lower():
                results.append(p)
        return results

    def has_plugin(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def count(self) -> int:
        return len(self._plugins)

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for pid, plugin in self._plugins.items():
            graph[pid] = [d.plugin_id for d in plugin.dependencies]
        return graph

    def get_dependents(self, plugin_id: str) -> List[str]:
        return [
            pid for pid, p in self._plugins.items()
            if any(d.plugin_id == plugin_id for d in p.dependencies)
        ]

    def aggregate_health(self) -> PluginEngineHealth:
        total = len(self._plugins)
        enabled = sum(1 for p in self._plugins.values() if p.state == PluginState.ENABLED)
        loaded = sum(1 for p in self._plugins.values() if p.is_loaded)
        failed = sum(1 for p in self._plugins.values() if p.state == PluginState.FAILED)
        disabled = sum(1 for p in self._plugins.values() if p.state == PluginState.DISABLED)
        total_crashes = sum(h.crash_count for h in self._health.values())
        return PluginEngineHealth(
            total_plugins=total,
            enabled_plugins=enabled,
            loaded_plugins=loaded,
            failed_plugins=failed,
            disabled_plugins=disabled,
            total_crashes=total_crashes,
        )

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
