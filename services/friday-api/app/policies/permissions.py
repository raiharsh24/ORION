from typing import Set, Optional

BUILTIN_SCOPES = {
    "admin": {"*"},
    "developer": {"read", "write", "execute", "terminal", "filesystem"},
    "operator": {"read", "write", "execute"},
    "viewer": {"read"},
}


class PermissionManager:
    """
    Validates user credentials and grants action clearance levels.
    """
    def __init__(self) -> None:
        self.scopes: Set[str] = set()

    async def has_permission(self, scope: str, role: Optional[str] = "viewer") -> bool:
        allowed = BUILTIN_SCOPES.get(role, BUILTIN_SCOPES["viewer"])
        if "*" in allowed:
            return True
        return scope in allowed
