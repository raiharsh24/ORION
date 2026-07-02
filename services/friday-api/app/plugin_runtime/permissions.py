from typing import Set, Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from loguru import logger

from app.plugin_runtime.security import SecurityConfig, SecurityPolicy
from app.plugins.base import Plugin, PluginPermission


class PermissionEnforcer:
    def __init__(self, security_config: Optional[SecurityConfig] = None) -> None:
        self._config = security_config or SecurityConfig()
        self._granted_permissions: Dict[str, Set[str]] = {}
        self._violations: List[Dict[str, Any]] = []

    def grant(self, plugin_id: str, permission_id: str) -> None:
        if plugin_id not in self._granted_permissions:
            self._granted_permissions[plugin_id] = set()
        self._granted_permissions[plugin_id].add(permission_id)

    def revoke(self, plugin_id: str, permission_id: str) -> None:
        perms = self._granted_permissions.get(plugin_id)
        if perms:
            perms.discard(permission_id)

    def is_granted(self, plugin_id: str, permission_id: str) -> bool:
        perms = self._granted_permissions.get(plugin_id)
        if perms is None:
            return False
        if permission_id in perms:
            return True
        if permission_id.endswith(".*"):
            prefix = permission_id[:-2]
            return any(p.startswith(prefix) for p in perms)
        if "*" in perms:
            return True
        return False

    def check_permission(self, plugin_id: str, plugin_name: str,
                         permission_id: str, detail: str = "") -> bool:
        if self.is_granted(plugin_id, permission_id):
            return True
        violation = {
            "plugin_id": plugin_id,
            "plugin_name": plugin_name,
            "permission": permission_id,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._violations.append(violation)
        logger.warning(f"Plugin '{plugin_name}' missing permission '{permission_id}': {detail}")
        return False

    def check_filesystem_access(self, plugin_id: str, plugin_name: str,
                                 path: str, write: bool = False) -> bool:
        perm = "filesystem.write" if write else "filesystem.read"
        if not self.is_granted(plugin_id, perm):
            return self.check_permission(plugin_id, plugin_name, perm, path)
        if self._config.filesystem and not self._config.filesystem.is_path_allowed(path, write):
            return self.check_permission(
                plugin_id, plugin_name, perm,
                f"Path not allowed: {path}",
            )
        return True

    def check_network_access(self, plugin_id: str, plugin_name: str,
                              host: str, port: int) -> bool:
        if not self.is_granted(plugin_id, "network"):
            return self.check_permission(
                plugin_id, plugin_name, "network", f"{host}:{port}",
            )
        if self._config.network:
            if not self._config.network.is_host_allowed(host):
                return self.check_permission(
                    plugin_id, plugin_name, "network",
                    f"Host not allowed: {host}",
                )
            if not self._config.network.is_port_allowed(port):
                return self.check_permission(
                    plugin_id, plugin_name, "network",
                    f"Port not allowed: {port}",
                )
        return True

    def check_import(self, plugin_id: str, plugin_name: str,
                      module_name: str) -> bool:
        if not self._config.imports:
            return True
        if not self._config.imports.is_import_allowed(module_name):
            return self.check_permission(
                plugin_id, plugin_name, "imports",
                f"Module not allowed: {module_name}",
            )
        return True

    def grant_from_manifest(self, plugin_id: str,
                             permissions: List[PluginPermission]) -> None:
        for perm in permissions:
            self.grant(plugin_id, perm.permission_id)

    def get_violations(self, plugin_id: Optional[str] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        if plugin_id:
            return [v for v in self._violations if v["plugin_id"] == plugin_id][:limit]
        return self._violations[:limit]

    def clear_violations(self, plugin_id: Optional[str] = None) -> None:
        if plugin_id:
            self._violations = [v for v in self._violations
                                if v["plugin_id"] != plugin_id]
        else:
            self._violations.clear()

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    def reset(self) -> None:
        self._granted_permissions.clear()
        self._violations.clear()
