import time
from typing import Optional, Any, Dict
from loguru import logger

from app.plugins.registry import PluginRegistry as SdkPluginRegistry
from app.plugin_runtime.base import PluginInstance, PluginRuntimeState
from app.plugin_runtime.events import PluginUnloaded, PluginFailed
from app.plugin_runtime.monitor import PluginMonitor
from app.plugin_runtime.permissions import PermissionEnforcer


class PluginUnloader:
    def __init__(
        self,
        sdk_registry: SdkPluginRegistry,
        monitor: PluginMonitor,
        permission_enforcer: PermissionEnforcer,
        event_bus: Optional[Any] = None,
        cleanup_on_unload: bool = True,
    ) -> None:
        self._sdk_registry = sdk_registry
        self._monitor = monitor
        self._perms = permission_enforcer
        self._event_bus = event_bus
        self._cleanup = cleanup_on_unload

    async def unload(self, inst: PluginInstance) -> bool:
        plugin_id = inst.plugin_id
        inst.record_state(PluginRuntimeState.UNLOADING)
        start = time.time()

        try:
            plugin_instance = inst.metadata.get("plugin_instance")
            if plugin_instance is not None:
                try:
                    await plugin_instance.on_disable()
                    await plugin_instance.on_unload()
                except Exception as e:
                    logger.warning(f"Plugin '{plugin_id}' lifecycle hooks error: {e}")

            self._cleanup_permissions(plugin_id)
            self._cleanup_monitor(plugin_id)

            sdk_removed = self._sdk_registry.remove(plugin_id)
            if not sdk_removed:
                logger.warning(f"Plugin '{plugin_id}' not found in SDK registry")

            cleanup_time = (time.time() - start) * 1000
            inst.record_state(PluginRuntimeState.UNLOADED)

            self._publish(PluginUnloaded(
                plugin_id=plugin_id, name=inst.name,
                cleanup_time_ms=cleanup_time,
            ))
            logger.info(f"Plugin '{plugin_id}' unloaded in {cleanup_time:.1f}ms")
            return True

        except Exception as e:
            error = str(e)
            inst.last_error = error
            inst.error_count += 1
            inst.record_state(PluginRuntimeState.FAILED, error)
            self._monitor.record_crash(plugin_id, inst.name, error, "unload")
            self._publish(PluginFailed(
                plugin_id=plugin_id, name=inst.name,
                error=error, stage="unload",
            ))
            return False

    async def cleanup(self, inst: PluginInstance) -> bool:
        if not self._cleanup:
            return True
        try:
            self._cleanup_permissions(inst.plugin_id)
            self._cleanup_monitor(inst.plugin_id)
            self._sdk_registry.remove(inst.plugin_id)
            inst.record_state(PluginRuntimeState.CLEANING)
            return True
        except Exception as e:
            logger.error(f"Cleanup failed for plugin '{inst.plugin_id}': {e}")
            return False

    def _cleanup_permissions(self, plugin_id: str) -> None:
        self._perms.clear_violations(plugin_id)

    def _cleanup_monitor(self, plugin_id: str) -> None:
        pass

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
