from typing import List
from app.plugins.base import PluginPermission


class PermissionValidator:
    def __init__(self) -> None:
        self._granted_permissions: dict = {}

    def grant(self, permission_id: str) -> None:
        self._granted_permissions[permission_id] = True

    def revoke(self, permission_id: str) -> None:
        self._granted_permissions.pop(permission_id, None)

    def is_granted(self, permission_id: str) -> bool:
        return self._granted_permissions.get(permission_id, False)

    def validate(self, permissions: List[PluginPermission]) -> List[str]:
        errors = []
        for perm in permissions:
            if not self.is_granted(perm.permission_id):
                errors.append(
                    f"Permission '{perm.permission_id}' is not granted"
                )
        return errors

    def validate_pre_install(self, permissions: List[PluginPermission]) -> List[str]:
        errors = []
        for perm in permissions:
            if not self.is_granted(perm.permission_id):
                errors.append(
                    f"Required permission '{perm.permission_id}' is not granted. "
                    f"Grant it first via PermissionValidator.grant()"
                )
        return errors
