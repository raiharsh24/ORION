from typing import Set, List

class PermissionManager:
    """
    Checks and grants access permissions for desktop execution categories.
    Supports permission checks for: File access, Process control, Desktop control.
    """
    def __init__(self) -> None:
        """Initialize the PermissionManager."""
        self._granted_permissions: Set[str] = {
            "file_access",
            "process_control",
            "desktop_control"
        }

    async def has_permission(self, permission: str) -> bool:
        """
        Checks if a specific permission category is granted.

        Args:
            permission (str): Permission code (e.g. 'file_access').

        Returns:
            bool: True if authorized.
        """
        return permission in self._granted_permissions

    async def grant_permission(self, permission: str) -> None:
        """
        Grants a permission.

        Args:
            permission (str): Permission code.
        """
        self._granted_permissions.add(permission)

    async def revoke_permission(self, permission: str) -> None:
        """
        Revokes a permission.

        Args:
            permission (str): Permission code.
        """
        self._granted_permissions.discard(permission)


class DesktopPermissionTracker(PermissionManager):
    """
    Tracker verifying runtime desktop permission credentials.
    """
    async def verify_permissions(self) -> List[str]:
        """
        Checks missing permissions list.

        Returns:
            List[str]: Missing permission codes.
        """
        missing = []
        for perm in ["file_access", "process_control", "desktop_control"]:
            if not await self.has_permission(perm):
                missing.append(perm)
        return missing
