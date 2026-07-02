import time
import asyncio
from typing import Optional, Any, Dict, List, Callable, Awaitable
from datetime import datetime, timezone
from loguru import logger

from app.plugins.registry import PluginRegistry as SdkPluginRegistry
from app.plugin_runtime.base import (
    PluginInstance, PluginRuntimeState, PluginRuntimeConfig,
    SandboxConfig, ResourceQuota,
)
from app.plugin_runtime.events import (
    PluginSuspended, PluginResumed, PluginFailed,
)
from app.plugin_runtime.sandbox import Sandbox
from app.plugin_runtime.loader import RuntimePluginLoader
from app.plugin_runtime.unloader import PluginUnloader
from app.plugin_runtime.reloader import PluginReloader
from app.plugin_runtime.monitor import PluginMonitor
from app.plugin_runtime.registry import PluginRuntimeRegistry
from app.plugin_runtime.permissions import PermissionEnforcer
from app.plugin_runtime.security import SecurityConfig
from app.plugin_runtime.health import PluginRuntimeHealth


class PluginRuntime:
    def __init__(
        self,
        sdk_registry: SdkPluginRegistry,
        event_bus: Optional[Any] = None,
        config: Optional[PluginRuntimeConfig] = None,
        security_config: Optional[SecurityConfig] = None,
    ) -> None:
        self._config = config or PluginRuntimeConfig()
        self._event_bus = event_bus
        self._start_time: float = time.time()

        self._permission_enforcer = PermissionEnforcer(security_config)
        self._sandbox = Sandbox(
            config=self._config.sandbox_config,
            permission_enforcer=self._permission_enforcer,
            security_config=security_config,
            event_bus=event_bus,
        )
        self._monitor = PluginMonitor()

        self._loader = RuntimePluginLoader(
            sdk_registry=sdk_registry,
            sandbox=self._sandbox,
            monitor=self._monitor,
            permission_enforcer=self._permission_enforcer,
            event_bus=event_bus,
            config=config,
        )
        self._unloader = PluginUnloader(
            sdk_registry=sdk_registry,
            monitor=self._monitor,
            permission_enforcer=self._permission_enforcer,
            event_bus=event_bus,
            cleanup_on_unload=config.cleanup_on_unload if config else True,
        )
        self._reloader = PluginReloader(
            loader=self._loader,
            unloader=self._unloader,
            monitor=self._monitor,
            event_bus=event_bus,
            config=config,
        )
        self._registry = PluginRuntimeRegistry(self._loader)

    @property
    def sandbox(self) -> Sandbox:
        return self._sandbox

    @property
    def loader(self) -> RuntimePluginLoader:
        return self._loader

    @property
    def unloader(self) -> PluginUnloader:
        return self._unloader

    @property
    def reloader(self) -> PluginReloader:
        return self._reloader

    @property
    def monitor(self) -> PluginMonitor:
        return self._monitor

    @property
    def registry(self) -> PluginRuntimeRegistry:
        return self._registry

    @property
    def permission_enforcer(self) -> PermissionEnforcer:
        return self._permission_enforcer

    async def start(self) -> None:
        logger.info("Plugin Runtime starting...")
        for plugin_dir in self._config.plugin_dirs:
            result = self._loader.load_from_directory(plugin_dir)
            logger.info(f"Discovered {result['total']} plugins in '{plugin_dir}'")
            if self._config.watch_enabled:
                await self._reloader.start_watching(plugin_dir)
            if self._config.auto_load:
                for plugin_id in result["discovered"]:
                    inst = await self._loader.load(plugin_id)
                    if inst:
                        await self._loader.initialize(plugin_id)
                        await self._loader.mark_ready(plugin_id)
                        if self._config.auto_enable:
                            logger.info(f"Plugin '{plugin_id}' loaded and ready")
        logger.info("Plugin Runtime started")

    async def shutdown(self) -> None:
        logger.info("Plugin Runtime shutting down...")
        await self._reloader.shutdown()
        for inst in list(self._loader.instances.values()):
            if inst.is_running or inst.state == PluginRuntimeState.SUSPENDED:
                await self._unloader.unload(inst)
        self._monitor.reset()
        logger.info("Plugin Runtime shut down")

    async def load_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        inst = await self._loader.load(plugin_id)
        if inst:
            await self._loader.initialize(plugin_id)
            await self._loader.mark_ready(plugin_id)
        return inst

    async def unload_plugin(self, plugin_id: str) -> bool:
        inst = self._loader.get_instance(plugin_id)
        if inst is None:
            return False
        result = await self._unloader.unload(inst)
        if result:
            self._loader.remove_instance(plugin_id)
        return result

    async def reload_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        return await self._reloader.reload(plugin_id)

    async def suspend_plugin(self, plugin_id: str,
                              reason: str = "") -> bool:
        inst = self._loader.get_instance(plugin_id)
        if inst is None or inst.state != PluginRuntimeState.READY:
            return False
        inst.record_state(PluginRuntimeState.SUSPENDED, reason)
        self._publish(PluginSuspended(
            plugin_id=plugin_id, name=inst.name, reason=reason,
        ))
        logger.info(f"Plugin '{plugin_id}' suspended: {reason}")
        return True

    async def resume_plugin(self, plugin_id: str) -> bool:
        inst = self._loader.get_instance(plugin_id)
        if inst is None or inst.state != PluginRuntimeState.SUSPENDED:
            return False
        inst.record_state(PluginRuntimeState.RESUMING)
        await self._loader.mark_ready(plugin_id)
        self._publish(PluginResumed(
            plugin_id=plugin_id, name=inst.name,
        ))
        logger.info(f"Plugin '{plugin_id}' resumed")
        return True

    async def execute(self, plugin_id: str, coro: Awaitable[Any],
                      timeout_ms: Optional[float] = None) -> Any:
        inst = self._loader.get_instance(plugin_id)
        if inst is None:
            raise ValueError(f"Plugin '{plugin_id}' not found")
        if inst.state != PluginRuntimeState.READY:
            raise RuntimeError(f"Plugin '{plugin_id}' not ready (state={inst.state.value})")

        start = time.time()
        inst.record_state(PluginRuntimeState.EXECUTING)

        try:
            result = await self._sandbox.execute(
                plugin_id, inst.name, coro, timeout_ms,
                inst.resource_quota,
            )
            duration = (time.time() - start) * 1000
            self._monitor.record_execution(plugin_id, duration, success=True)
            inst.record_state(PluginRuntimeState.READY)
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._monitor.record_execution(plugin_id, duration, success=False)
            error = str(e)
            inst.last_error = error
            inst.error_count += 1
            if inst.error_count >= self._config.crash_threshold:
                inst.record_state(PluginRuntimeState.FAILED, error)
                self._monitor.record_crash(plugin_id, inst.name, error, "execute")
                self._publish(PluginFailed(
                    plugin_id=plugin_id, name=inst.name,
                    error=error, stage="execute",
                ))
            else:
                inst.record_state(PluginRuntimeState.READY)
            raise

    def health(self) -> PluginRuntimeHealth:
        return self._monitor.get_health(self._loader.instances)

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self._event_bus.publish(event))
            except RuntimeError:
                pass
            except Exception:
                pass
