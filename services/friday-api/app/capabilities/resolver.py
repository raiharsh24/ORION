import time
from typing import Dict, List, Optional, Set, Any
from loguru import logger

from app.capabilities.base import (
    CapabilityDefinition, CapabilityResolution, CapabilityResult,
    CapabilityStatus, CapabilityCategory,
)
from app.capabilities.registry import CapabilityRegistry
from app.capabilities.events import CapabilityResolved, CapabilityExecuted
from app.tool_selection.base import (
    ToolSelectionContext, ToolSelectionResult,
)
from app.tool_selection.selector import ToolSelectionEngine


class CapabilityResolver:
    def __init__(
        self,
        registry: CapabilityRegistry,
        tool_selection_engine: ToolSelectionEngine,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._tool_selection = tool_selection_engine
        self._event_bus = event_bus

    def resolve(
        self,
        capability_id: str,
        selection_context: Optional[ToolSelectionContext] = None,
    ) -> CapabilityResolution:
        t0 = time.time()

        defn = self._registry.resolve_alias(capability_id)
        if defn is None:
            return CapabilityResolution(
                capability_id=capability_id,
                capability_name=capability_id,
                errors=[f"Capability '{capability_id}' not found"],
            )

        if defn.status != CapabilityStatus.ACTIVE:
            return CapabilityResolution(
                capability_id=defn.id,
                capability_name=defn.name,
                errors=[f"Capability '{defn.id}' is not active (status: {defn.status.value})"],
            )

        unresolved_deps = self._check_dependencies(defn)
        if unresolved_deps:
            return CapabilityResolution(
                capability_id=defn.id,
                capability_name=defn.name,
                errors=[f"Unresolved dependencies: {', '.join(unresolved_deps)}"],
            )

        resolved_tools = list(defn.tool_ids)
        recommended_tools = list(defn.recommended_tool_ids)
        all_deps = self._collect_transitive_dependencies(defn)

        ctx = selection_context or ToolSelectionContext()
        if defn.category:
            if defn.category.value not in ctx.required_categories:
                ctx.required_categories = list(ctx.required_categories) + [defn.category.value]

        elapsed = (time.time() - t0) * 1000

        self._registry.record_resolution()
        self._publish(CapabilityResolved(
            capability_id=defn.id,
            name=defn.name,
            resolved_tools=len(resolved_tools),
            duration_ms=elapsed,
        ))

        return CapabilityResolution(
            capability_id=defn.id,
            capability_name=defn.name,
            resolved_tool_ids=resolved_tools,
            resolved_dependencies=all_deps,
            confidence=1.0 if len(resolved_tools) > 0 else 0.5,
            resolution_time_ms=elapsed,
        )

    async def resolve_with_selection(
        self,
        capability_id: str,
        selection_context: Optional[ToolSelectionContext] = None,
    ) -> ToolSelectionResult:
        resolution = self.resolve(capability_id, selection_context)

        if resolution.errors:
            return ToolSelectionResult(
                errors=resolution.errors,
                confidence=0.0,
            )

        ctx = selection_context or ToolSelectionContext()
        ctx.required_capabilities = list(ctx.required_capabilities) + [capability_id]

        return await self._tool_selection.select(ctx)

    def resolve_multi(
        self,
        capability_ids: List[str],
        selection_context: Optional[ToolSelectionContext] = None,
    ) -> Dict[str, CapabilityResolution]:
        results: Dict[str, CapabilityResolution] = {}
        visited: Set[str] = set()

        def resolve_with_deps(cid: str) -> None:
            if cid in visited:
                return
            visited.add(cid)
            defn = self._registry.resolve_alias(cid)
            if defn is None:
                results[cid] = CapabilityResolution(
                    capability_id=cid, capability_name=cid,
                    errors=[f"Capability '{cid}' not found"],
                )
                return
            for dep in defn.dependencies:
                resolve_with_deps(dep.capability_id)
            results[cid] = self.resolve(cid, selection_context)

        for cid in capability_ids:
            resolve_with_deps(cid)

        return results

    def _collect_transitive_dependencies(self, defn: CapabilityDefinition) -> List[str]:
        collected: List[str] = []
        visited: Set[str] = set()

        def collect(cid: str) -> None:
            if cid in visited:
                return
            visited.add(cid)
            dep_defn = self._registry.get(cid)
            if dep_defn is None:
                return
            for sub_dep in dep_defn.dependencies:
                if sub_dep.capability_id not in collected:
                    collected.append(sub_dep.capability_id)
                collect(sub_dep.capability_id)

        for dep in defn.dependencies:
            if dep.capability_id not in collected:
                collected.append(dep.capability_id)
            collect(dep.capability_id)

        return collected

    def _check_dependencies(self, defn: CapabilityDefinition) -> List[str]:
        unresolved: List[str] = []
        for dep in defn.dependencies:
            dep_defn = self._registry.get(dep.capability_id)
            if dep_defn is None:
                if not dep.optional:
                    unresolved.append(dep.capability_id)
                continue
            if dep_defn.status != CapabilityStatus.ACTIVE and not dep.optional:
                unresolved.append(
                    f"{dep.capability_id} (status: {dep_defn.status.value})"
                )
        return unresolved

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
