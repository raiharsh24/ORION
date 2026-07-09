import time
import json
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone
from loguru import logger

from app.plugins.base import Plugin, PluginState, PluginManifest
from app.plugins.manifest import parse_manifest, validate_manifest
from app.plugins.registry import PluginRegistry as SdkPluginRegistry
from app.plugin_runtime.base import (
    PluginInstance, PluginRuntimeState, PluginRuntimeConfig,
)
from app.plugin_runtime.events import (
    PluginDiscovered, PluginValidated, PluginLoaded, PluginFailed,
    PluginInitialized, PluginReady,
)
from app.plugin_runtime.sandbox import Sandbox
from app.plugin_runtime.monitor import PluginMonitor
from app.plugin_runtime.permissions import PermissionEnforcer


class RuntimePluginLoader:
    def __init__(
        self,
        sdk_registry: SdkPluginRegistry,
        sandbox: Sandbox,
        monitor: PluginMonitor,
        permission_enforcer: PermissionEnforcer,
        event_bus: Optional[Any] = None,
        config: Optional[PluginRuntimeConfig] = None,
    ) -> None:
        self._sdk_registry = sdk_registry
        self._sandbox = sandbox
        self._monitor = monitor
        self._perms = permission_enforcer
        self._event_bus = event_bus
        self._config = config or PluginRuntimeConfig()
        self._instances: Dict[str, PluginInstance] = {}
        self._discovered_paths: Dict[str, str] = {}

    @property
    def instances(self) -> Dict[str, PluginInstance]:
        return self._instances

    def get_instance(self, plugin_id: str) -> Optional[PluginInstance]:
        return self._instances.get(plugin_id)

    def discover(self, plugin_dir: str) -> List[str]:
        base = Path(plugin_dir)
        if not base.exists():
            logger.warning(f"Plugin directory '{plugin_dir}' does not exist")
            return []

        discovered = []
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            manifest = self._find_manifest(entry)
            if manifest is None:
                continue
            try:
                parsed = parse_manifest(Path(manifest))
                errors = validate_manifest(parsed)
                if errors:
                    logger.warning(f"Plugin '{parsed.id}' manifest invalid: {errors}")
                    continue
                plugin_id = parsed.id
                if plugin_id in self._instances:
                    logger.debug(f"Plugin '{plugin_id}' already loaded, skipping")
                    continue
                inst = PluginInstance(
                    plugin_id=plugin_id,
                    name=parsed.name,
                    version=parsed.version,
                    manifest_path=str(manifest),
                    plugin_dir=str(entry),
                    entry_point=parsed.entry_point or "",
                    dependencies=[d.plugin_id for d in parsed.dependencies],
                    metadata={
                        "author": parsed.author,
                        "description": parsed.description,
                        "required_capabilities": list(parsed.required_capabilities),
                    },
                )
                inst.record_state(PluginRuntimeState.DISCOVERED)
                self._instances[plugin_id] = inst
                self._discovered_paths[plugin_id] = str(entry)
                discovered.append(plugin_id)
                self._publish(PluginDiscovered(
                    plugin_id=plugin_id, name=parsed.name, path=str(entry),
                ))
                logger.info(f"Discovered plugin '{plugin_id}' at '{entry}'")
            except Exception as e:
                logger.error(f"Failed to discover plugin at '{entry}': {e}")
                continue
        return discovered

    def _import_plugin_module(self, inst: PluginInstance) -> Optional[Any]:
        plugin_dir = inst.plugin_dir
        if not plugin_dir:
            return None
        entry = inst.entry_point or "main"
        module_path = str(Path(plugin_dir) / f"{entry}.py")
        if not Path(module_path).exists():
            logger.warning(f"Plugin '{inst.plugin_id}' entry point '{entry}.py' not found at '{module_path}'")
            return None
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{inst.plugin_id}", module_path,
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for plugin '{inst.plugin_id}'")
                return None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{inst.plugin_id}"] = mod
            spec.loader.exec_module(mod)

            from app.plugin_sdk.base_plugin import BasePlugin
            plugin_class = None
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                    plugin_class = attr
                    break

            if plugin_class is None:
                logger.warning(f"No BasePlugin subclass found in '{module_path}'")
                return None

            instance = plugin_class()
            instance.id = inst.plugin_id
            instance.name = inst.name
            return instance

        except Exception as e:
            logger.error(f"Failed to import plugin module '{module_path}': {e}")
            return None

    async def load(self, plugin_id: str) -> Optional[PluginInstance]:
        inst = self._instances.get(plugin_id)
        if inst is None:
            logger.error(f"Plugin '{plugin_id}' not discovered")
            return None
        if not inst.is_loadable:
            logger.warning(f"Plugin '{plugin_id}' in state '{inst.state.value}' cannot be loaded")
            return None

        inst.record_state(PluginRuntimeState.LOADING)
        start = time.time()

        try:
            if inst.manifest_path:
                parsed = parse_manifest(Path(inst.manifest_path))
                errors = validate_manifest(parsed)
                if errors:
                    raise ValueError(f"Manifest validation failed: {errors}")
                inst.record_state(PluginRuntimeState.VALIDATED)
                self._publish(PluginValidated(
                    plugin_id=plugin_id, name=inst.name,
                    valid=True, errors=[],
                ))

            sdk_plugin = self._sdk_registry.install(parsed)
            if sdk_plugin is None:
                existing = self._sdk_registry.get(plugin_id)
                if existing is None:
                    raise RuntimeError(f"Failed to install plugin '{plugin_id}' in SDK registry")
                sdk_plugin = existing

            self._perms.grant_from_manifest(plugin_id, list(parsed.permissions))

            if parsed.dependencies:
                for dep in parsed.dependencies:
                    if not dep.optional:
                        dep_inst = self._instances.get(dep.plugin_id)
                        if dep_inst is None or dep_inst.state != PluginRuntimeState.READY:
                            raise RuntimeError(
                                f"Dependency '{dep.plugin_id}' not ready for plugin '{plugin_id}'"
                            )

            plugin_instance = self._import_plugin_module(inst)
            inst.metadata["plugin_instance"] = plugin_instance

            load_time = (time.time() - start) * 1000
            inst.loaded_at = datetime.now(timezone.utc)
            inst.record_state(PluginRuntimeState.LOADED)
            self._monitor.record_load(plugin_id, load_time)

            self._publish(PluginLoaded(
                plugin_id=plugin_id, name=inst.name,
                version=inst.version, load_time_ms=load_time,
            ))
            logger.info(f"Plugin '{plugin_id}' loaded in {load_time:.1f}ms")
            return inst

        except Exception as e:
            error = str(e)
            inst.last_error = error
            inst.error_count += 1
            inst.record_state(PluginRuntimeState.FAILED, error)
            self._monitor.record_crash(plugin_id, inst.name, error, "load")
            self._publish(PluginFailed(
                plugin_id=plugin_id, name=inst.name,
                error=error, stage="load",
            ))
            return None

    async def initialize(self, plugin_id: str) -> bool:
        inst = self._instances.get(plugin_id)
        if inst is None or inst.state != PluginRuntimeState.LOADED:
            return False

        inst.record_state(PluginRuntimeState.INITIALIZING)
        start = time.time()

        try:
            plugin_instance = inst.metadata.get("plugin_instance")
            if plugin_instance is not None:
                from app.plugin_sdk.plugin_context import PluginContext
                ctx = PluginContext(
                    plugin_id=inst.plugin_id,
                    plugin_name=inst.name,
                    event_bus=self._event_bus,
                    config=inst.metadata.get("config", {}),
                )
                plugin_instance.set_context(ctx)
                await plugin_instance.on_load()

            init_time = (time.time() - start) * 1000
            inst.initialized_at = datetime.now(timezone.utc)
            inst.record_state(PluginRuntimeState.INITIALIZED)
            self._publish(PluginInitialized(
                plugin_id=plugin_id, name=inst.name, init_time_ms=init_time,
            ))
            return True
        except Exception as e:
            error = str(e)
            inst.last_error = error
            inst.error_count += 1
            inst.record_state(PluginRuntimeState.FAILED, error)
            self._monitor.record_crash(plugin_id, inst.name, error, "initialize")
            self._publish(PluginFailed(
                plugin_id=plugin_id, name=inst.name,
                error=error, stage="initialize",
            ))
            return False

    async def mark_ready(self, plugin_id: str,
                          tool_count: int = 0, cap_count: int = 0) -> bool:
        inst = self._instances.get(plugin_id)
        if inst is None:
            return False
        inst.record_state(PluginRuntimeState.READY)
        inst.ready_at = datetime.now(timezone.utc)
        self._monitor.set_peak_plugins(len(self._instances))

        plugin_instance = inst.metadata.get("plugin_instance")
        if plugin_instance is not None:
            try:
                await plugin_instance.on_enable()
            except Exception as e:
                logger.warning(f"Plugin '{plugin_id}' on_enable failed: {e}")

        self._publish(PluginReady(
            plugin_id=plugin_id, name=inst.name,
            tool_count=tool_count, cap_count=cap_count,
        ))
        logger.info(f"Plugin '{plugin_id}' is READY")
        return True

    def load_from_directory(self, plugin_dir: str) -> Dict[str, Any]:
        discovered = self.discover(plugin_dir)
        return {"discovered": discovered, "total": len(discovered)}

    def _find_manifest(self, directory: Path) -> Optional[Path]:
        for name in ("plugin.json", "manifest.json"):
            p = directory / name
            if p.exists():
                return p
        return None

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    pass
            except Exception:
                pass

    def remove_instance(self, plugin_id: str) -> bool:
        if plugin_id in self._instances:
            del self._instances[plugin_id]
            self._discovered_paths.pop(plugin_id, None)
            return True
        return False
