import time
import asyncio
from typing import Optional, Any, Callable, Awaitable, Dict
from loguru import logger

from app.plugin_runtime.base import SandboxConfig, ResourceQuota
from app.plugin_runtime.permissions import PermissionEnforcer
from app.plugin_runtime.events import PluginSandboxViolation, PluginResourceWarning
from app.plugin_runtime.security import SecurityConfig


class Sandbox:
    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        permission_enforcer: Optional[PermissionEnforcer] = None,
        security_config: Optional[SecurityConfig] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._config = config or SandboxConfig()
        self._perms = permission_enforcer or PermissionEnforcer(security_config)
        self._security = security_config or SecurityConfig()
        self._event_bus = event_bus

    @property
    def permission_enforcer(self) -> PermissionEnforcer:
        return self._perms

    async def execute(
        self,
        plugin_id: str,
        plugin_name: str,
        coro: Awaitable[Any],
        timeout_ms: Optional[float] = None,
        resource_quota: Optional[ResourceQuota] = None,
    ) -> Any:
        quota = resource_quota or self._config.resource_quota
        effective_timeout = timeout_ms or quota.max_execution_time_ms or self._config.execution_timeout_ms
        effective_timeout = min(effective_timeout, self._config.execution_timeout_ms)
        timeout_seconds = effective_timeout / 1000.0

        try:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            msg = f"Plugin '{plugin_name}' execution timed out after {effective_timeout}ms"
            logger.warning(msg)
            await self._publish_violation(plugin_id, plugin_name, "timeout", msg)
            raise TimeoutError(msg)

    async def execute_sync(
        self,
        plugin_id: str,
        plugin_name: str,
        fn: Callable[[], Any],
        timeout_ms: Optional[float] = None,
        resource_quota: Optional[ResourceQuota] = None,
    ) -> Any:
        loop = asyncio.get_event_loop()
        return await self.execute(
            plugin_id, plugin_name,
            loop.run_in_executor(None, fn),
            timeout_ms, resource_quota,
        )

    async def check_filesystem_access(
        self, plugin_id: str, plugin_name: str,
        path: str, write: bool = False,
    ) -> bool:
        if not self._config.restrict_filesystem:
            return True
        allowed = self._perms.check_filesystem_access(
            plugin_id, plugin_name, path, write,
        )
        if not allowed:
            await self._publish_violation(
                plugin_id, plugin_name,
                "filesystem" if not write else "filesystem_write",
                f"Access to '{path}' denied",
            )
        return allowed

    async def check_network_access(
        self, plugin_id: str, plugin_name: str,
        host: str, port: int,
    ) -> bool:
        if not self._config.restrict_network:
            return True
        allowed = self._perms.check_network_access(
            plugin_id, plugin_name, host, port,
        )
        if not allowed:
            await self._publish_violation(
                plugin_id, plugin_name, "network",
                f"Access to '{host}:{port}' denied",
            )
        return allowed

    async def check_import(
        self, plugin_id: str, plugin_name: str,
        module_name: str,
    ) -> bool:
        if not self._config.restrict_imports:
            return True
        allowed = self._perms.check_import(
            plugin_id, plugin_name, module_name,
        )
        if not allowed:
            await self._publish_violation(
                plugin_id, plugin_name, "import",
                f"Module '{module_name}' not allowed",
            )
        return allowed

    async def check_subprocess_allowed(
        self, plugin_id: str, plugin_name: str,
    ) -> bool:
        if not self._config.restrict_subprocess:
            return True
        allowed = self._perms.check_permission(
            plugin_id, plugin_name, "subprocess",
            "Subprocess execution restricted",
        )
        if not allowed:
            await self._publish_violation(
                plugin_id, plugin_name, "subprocess",
                "Subprocess execution denied",
            )
        return allowed

    async def _publish_violation(
        self, plugin_id: str, plugin_name: str,
        vtype: str, detail: str,
    ) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(PluginSandboxViolation(
                    plugin_id=plugin_id, name=plugin_name,
                    violation_type=vtype, detail=detail,
                ))
            except Exception:
                pass

    async def _publish_resource_warning(
        self, plugin_id: str, plugin_name: str,
        resource: str, usage: float, limit: float,
    ) -> None:
        if self._event_bus:
            try:
                await self._event_bus.publish(PluginResourceWarning(
                    plugin_id=plugin_id, name=plugin_name,
                    resource=resource, usage=usage, limit=limit,
                ))
            except Exception:
                pass

    def validate_imports(self, imports: Dict[str, Any]) -> bool:
        if not self._config.restrict_imports:
            return True
        for mod_name in imports:
            if not self._security.imports.is_import_allowed(mod_name):
                logger.warning(f"Import '{mod_name}' blocked by sandbox")
                return False
        return True

    @property
    def violation_count(self) -> int:
        return self._perms.violation_count

    def reset(self) -> None:
        self._perms.reset()
