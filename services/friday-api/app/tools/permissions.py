from typing import Dict, Set, Optional
from loguru import logger

from app.tools.base import PermissionLevel


class PermissionRegistry:
    def __init__(self) -> None:
        self._tool_permissions: Dict[str, PermissionLevel] = {}

    def register(self, tool_id: str, level: PermissionLevel) -> None:
        self._tool_permissions[tool_id] = level
        logger.debug(f"Permission for tool '{tool_id}' set to {level.value}")

    def remove(self, tool_id: str) -> None:
        self._tool_permissions.pop(tool_id, None)

    def get_permission(self, tool_id: str) -> Optional[PermissionLevel]:
        return self._tool_permissions.get(tool_id)

    def get_tools_by_permission(self, level: PermissionLevel) -> Set[str]:
        return {
            tid for tid, lvl in self._tool_permissions.items()
            if lvl == level
        }

    def has_permission(self, tool_id: str, required: PermissionLevel) -> bool:
        actual = self._tool_permissions.get(tool_id)
        if actual is None:
            return False
        levels = [PermissionLevel.USER, PermissionLevel.ELEVATED, PermissionLevel.ADMIN, PermissionLevel.SYSTEM]
        return levels.index(actual) >= levels.index(required)

    def clear(self) -> None:
        self._tool_permissions.clear()

    @property
    def count(self) -> int:
        return len(self._tool_permissions)
