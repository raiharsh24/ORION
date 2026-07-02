from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone


@dataclass
class AgentPermission:
    resource: str
    action: str
    granted: bool = True
    reason: str = ""


class PermissionManager:
    def __init__(self):
        self._agent_permissions: Dict[str, List[AgentPermission]] = {}
        self._role_permissions: Dict[str, List[AgentPermission]] = {}

    def grant(self, agent_id: str, resource: str, action: str) -> None:
        if agent_id not in self._agent_permissions:
            self._agent_permissions[agent_id] = []
        self._agent_permissions[agent_id].append(
            AgentPermission(resource=resource, action=action, granted=True,
                            reason="Granted by PermissionManager")
        )

    def revoke(self, agent_id: str, resource: str, action: str) -> bool:
        if agent_id not in self._agent_permissions:
            return False
        perms = self._agent_permissions[agent_id]
        for p in perms:
            if p.resource == resource and p.action == action:
                p.granted = False
                p.reason = "Revoked by PermissionManager"
                return True
        return False

    def check(self, agent_id: str, resource: str, action: str) -> bool:
        if agent_id not in self._agent_permissions:
            return False
        return any(
            p.resource == resource and p.action == action and p.granted
            for p in self._agent_permissions[agent_id]
        )

    def get_permissions(self, agent_id: str) -> List[AgentPermission]:
        return list(self._agent_permissions.get(agent_id, []))

    def set_role_permissions(self, role: str,
                             permissions: List[AgentPermission]) -> None:
        self._role_permissions[role] = permissions

    def get_role_permissions(self, role: str) -> List[AgentPermission]:
        return list(self._role_permissions.get(role, []))

    def grant_role_permission(self, role: str, resource: str, action: str) -> None:
        if role not in self._role_permissions:
            self._role_permissions[role] = []
        self._role_permissions[role].append(
            AgentPermission(resource=resource, action=action, granted=True,
                            reason=f"Role {role} permission")
        )

    def apply_role_permissions(self, agent_id: str, role: str) -> int:
        count = 0
        for perm in self.get_role_permissions(role):
            if not any(
                p.resource == perm.resource and p.action == perm.action
                for p in self._agent_permissions.get(agent_id, [])
            ):
                self.grant(agent_id, perm.resource, perm.action)
                count += 1
        return count

    def clear_agent(self, agent_id: str) -> None:
        self._agent_permissions.pop(agent_id, None)

    def list_agents(self) -> List[str]:
        return list(self._agent_permissions.keys())
