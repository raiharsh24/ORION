from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime, timezone
from loguru import logger

from app.capabilities.base import (
    CapabilityDefinition, CapabilityMetadata, CapabilityHealth,
    CapabilityPermission, CapabilityCategory, CapabilityStatus,
    CapabilityDependency,
)
from app.capabilities.events import (
    CapabilityRegistered, CapabilityRemoved, CapabilityHealthChanged,
)
from app.capabilities.metadata import build_metadata
from app.capabilities.health import CapabilityEngineHealth


class CapabilityRegistry:
    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._definitions: Dict[str, CapabilityDefinition] = {}
        self._permissions: Dict[str, CapabilityPermission] = {}
        self._health: Dict[str, CapabilityHealth] = {}
        self._alias_map: Dict[str, str] = {}
        self._resolved_count = 0
        self._execution_count = 0
        self._failure_count = 0

    def register(self, definition: CapabilityDefinition,
                 permission: Optional[CapabilityPermission] = None) -> None:
        existing = self._definitions.get(definition.id)
        old_status = existing.status.value if existing else None

        self._definitions[definition.id] = definition
        for alias in definition.aliases:
            self._alias_map[alias] = definition.id

        if permission:
            self._permissions[definition.id] = permission
        elif definition.id not in self._permissions:
            self._permissions[definition.id] = CapabilityPermission(
                capability_id=definition.id,
                required_level=definition.permission_level,
            )

        if definition.id not in self._health:
            self._health[definition.id] = CapabilityHealth(
                availability=True,
                status=definition.status.value,
                version=definition.version,
            )

        self._publish(CapabilityRegistered(
            capability_id=definition.id,
            name=definition.name,
            category=definition.category.value,
            version=definition.version,
        ))

    def unregister(self, capability_id: str) -> bool:
        defn = self._definitions.pop(capability_id, None)
        if defn is None:
            return False
        for alias in list(self._alias_map.keys()):
            if self._alias_map[alias] == capability_id:
                del self._alias_map[alias]
        self._permissions.pop(capability_id, None)
        self._health.pop(capability_id, None)
        self._publish(CapabilityRemoved(
            capability_id=capability_id,
            name=defn.name,
        ))
        return True

    def get(self, capability_id: str) -> Optional[CapabilityDefinition]:
        return self._definitions.get(capability_id)

    def get_by_alias(self, alias: str) -> Optional[CapabilityDefinition]:
        cap_id = self._alias_map.get(alias)
        if cap_id is None:
            return None
        return self._definitions.get(cap_id)

    def resolve_alias(self, name_or_id: str) -> Optional[CapabilityDefinition]:
        defn = self._definitions.get(name_or_id)
        if defn is not None:
            return defn
        cap_id = self._alias_map.get(name_or_id)
        if cap_id is not None:
            return self._definitions.get(cap_id)
        return None

    def get_metadata(self, capability_id: str) -> Optional[CapabilityMetadata]:
        defn = self.get(capability_id)
        if defn is None:
            return None
        return build_metadata(defn)

    def list_capabilities(self) -> List[CapabilityDefinition]:
        return list(self._definitions.values())

    def list_metadata(self) -> List[CapabilityMetadata]:
        return [build_metadata(d) for d in self._definitions.values()]

    def list_by_category(self, category: CapabilityCategory) -> List[CapabilityDefinition]:
        return [d for d in self._definitions.values() if d.category == category]

    def list_by_status(self, status: CapabilityStatus) -> List[CapabilityDefinition]:
        return [d for d in self._definitions.values() if d.status == status]

    def search(self, query: str) -> List[CapabilityDefinition]:
        q = query.lower()
        results = []
        for d in self._definitions.values():
            if q in d.id.lower() or q in d.name.lower() or q in d.description.lower():
                results.append(d)
                continue
            for alias in d.aliases:
                if q in alias.lower():
                    results.append(d)
                    break
            for tag in d.tags:
                if q in tag.lower():
                    results.append(d)
                    break
        return results

    def get_health(self, capability_id: str) -> Optional[CapabilityHealth]:
        return self._health.get(capability_id)

    def update_health(self, capability_id: str,
                      success: bool = True, duration_ms: float = 0.0) -> None:
        health = self._health.get(capability_id)
        if health is None:
            return
        health.last_execution = datetime.now(timezone.utc)
        if success:
            health.execution_success_count += 1
        else:
            health.execution_failure_count += 1

        total = health.execution_success_count + health.execution_failure_count
        if total > 0:
            old_status = health.status
            health.status = "healthy" if health.execution_failure_count == 0 else "degraded"
            if health.execution_failure_count > total * 0.5:
                health.status = "unhealthy"
            if health.status != old_status:
                defn = self._definitions.get(capability_id)
                if defn:
                    self._publish(CapabilityHealthChanged(
                        capability_id=capability_id,
                        name=defn.name,
                        old_status=old_status,
                        new_status=health.status,
                    ))

    def set_availability(self, capability_id: str, available: bool,
                         message: str = "") -> None:
        health = self._health.get(capability_id)
        if health is None:
            return
        old_status = health.status
        health.availability = available
        health.status = "available" if available else "unavailable"
        health.message = message
        if health.status != old_status:
            defn = self._definitions.get(capability_id)
            if defn:
                self._publish(CapabilityHealthChanged(
                    capability_id=capability_id,
                    name=defn.name,
                    old_status=old_status,
                    new_status=health.status,
                ))

    def get_permission(self, capability_id: str) -> Optional[CapabilityPermission]:
        return self._permissions.get(capability_id)

    def get_dependencies(self, capability_id: str) -> List[CapabilityDependency]:
        defn = self._definitions.get(capability_id)
        if defn is None:
            return []
        return list(defn.dependencies)

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for cid, defn in self._definitions.items():
            graph[cid] = [d.capability_id for d in defn.dependencies]
        return graph

    def has_capability(self, capability_id: str) -> bool:
        return capability_id in self._definitions

    def count(self) -> int:
        return len(self._definitions)

    def aggregate_health(self) -> CapabilityEngineHealth:
        total = len(self._definitions)
        active = sum(1 for d in self._definitions.values() if d.status == CapabilityStatus.ACTIVE)
        deprecated = sum(1 for d in self._definitions.values() if d.status == CapabilityStatus.DEPRECATED)
        disabled = sum(1 for d in self._definitions.values() if d.status == CapabilityStatus.DISABLED)
        total_exec = self._execution_count + self._failure_count
        success_rate = 100.0
        if total_exec > 0:
            success_rate = round((self._execution_count / total_exec) * 100, 2)
        return CapabilityEngineHealth(
            total_capabilities=total,
            active_capabilities=active,
            deprecated_capabilities=deprecated,
            disabled_capabilities=disabled,
            resolved_count=self._resolved_count,
            execution_count=self._execution_count,
            failure_count=self._failure_count,
            success_rate=success_rate,
            details={
                "unhealthy": sum(1 for h in self._health.values() if h.status == "unhealthy"),
                "unavailable": sum(1 for h in self._health.values() if not h.availability),
            },
        )

    def record_resolution(self) -> None:
        self._resolved_count += 1

    def record_execution(self, success: bool) -> None:
        if success:
            self._execution_count += 1
        else:
            self._failure_count += 1

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
