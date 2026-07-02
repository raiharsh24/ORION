import time
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

from app.plugins.base import (
    Plugin, PluginState, PluginManifest, PluginVersion,
)
from app.plugins.manifest import parse_manifest, validate_manifest, manifest_from_dict
from app.plugins.registry import PluginRegistry
from app.plugins.events import PluginLoaded, PluginFailed, PluginUnloaded
from app.plugins.permissions import PermissionValidator


class PluginLoader:
    def __init__(
        self,
        registry: PluginRegistry,
        permission_validator: PermissionValidator,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._permissions = permission_validator
        self._event_bus = event_bus

    def load_from_directory(self, directory: str) -> Dict[str, List[str]]:
        results: Dict[str, List[str]] = {"loaded": [], "failed": [], "skipped": []}
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            logger.warning(f"Plugin directory not found: {directory}")
            return results

        for entry in sorted(path.iterdir()):
            if entry.is_dir():
                manifest_path = entry / "plugin.json"
                if not manifest_path.exists():
                    manifest_path = entry / "manifest.json"
                if not manifest_path.exists():
                    continue

                manifest = parse_manifest(manifest_path)
                if manifest is None:
                    results["failed"].append(f"{entry.name}: invalid manifest")
                    continue

                load_result = self.load_plugin(manifest, str(entry))
                if load_result is None:
                    results["failed"].append(manifest.id)
                else:
                    results["loaded"].append(manifest.id)

        return results

    def load_plugin(self, manifest: PluginManifest,
                    source_path: str = "") -> Optional[Plugin]:
        validation_errors = validate_manifest(manifest)
        if validation_errors:
            logger.error(f"Plugin '{manifest.id}' manifest invalid: {validation_errors}")
            return None

        perm_errors = self._permissions.validate_pre_install(manifest.permissions)
        if perm_errors:
            logger.error(f"Plugin '{manifest.id}' permission check failed: {perm_errors}")
            return None

        existing = self._registry.get(manifest.id)
        if existing is not None:
            logger.warning(f"Plugin '{manifest.id}' already loaded")
            return None

        plugin = self._registry.install(manifest)
        if plugin is None:
            return None

        if not self._resolve_dependencies(plugin):
            self._registry.update_state(manifest.id, PluginState.FAILED,
                                        error="Unresolved dependencies")
            self._publish(PluginFailed(
                plugin_id=manifest.id, name=manifest.name,
                error="Unresolved dependencies",
            ))
            return None

        self._registry.update_state(manifest.id, PluginState.LOADED)
        self._publish(PluginLoaded(
            plugin_id=manifest.id, name=manifest.name,
            load_time_ms=0.0,
        ))
        return plugin

    def enable_plugin(self, plugin_id: str) -> bool:
        plugin = self._registry.get(plugin_id)
        if plugin is None:
            return False
        if plugin.state == PluginState.ENABLED:
            return True
        self._registry.update_state(plugin_id, PluginState.ENABLED)
        return True

    def disable_plugin(self, plugin_id: str) -> bool:
        plugin = self._registry.get(plugin_id)
        if plugin is None:
            return False
        self._registry.update_state(plugin_id, PluginState.DISABLED)
        return True

    def unload_plugin(self, plugin_id: str) -> bool:
        plugin = self._registry.get(plugin_id)
        if plugin is None:
            return False
        self._registry.update_state(plugin_id, PluginState.UNLOADED)
        self._publish(PluginUnloaded(
            plugin_id=plugin_id, name=plugin.name,
        ))
        return True

    def _resolve_dependencies(self, plugin: Plugin) -> bool:
        for dep in plugin.dependencies:
            dep_plugin = self._registry.get(dep.plugin_id)
            if dep_plugin is None:
                if not dep.optional:
                    logger.error(
                        f"Plugin '{plugin.id}' missing dependency: '{dep.plugin_id}'"
                    )
                    return False
                continue
            if not dep_plugin.is_enabled and not dep.optional:
                logger.error(
                    f"Dependency '{dep.plugin_id}' for plugin '{plugin.id}' "
                    f"is not enabled (state: {dep_plugin.state.value})"
                )
                return False
        return True

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
