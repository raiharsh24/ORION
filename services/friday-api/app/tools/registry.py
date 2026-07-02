from typing import Dict, List, Optional, Set, Callable, Any
from loguru import logger

from app.tools.base import (
    ToolDefinition, ToolCategory, PermissionLevel, ToolHealth, ToolDependency,
)
from app.tools.metadata import ToolMetadata
from app.tools.permissions import PermissionRegistry
from app.tools.health import ToolRegistryHealth
from app.tools.events import ToolRegistered, ToolRemoved, ToolHealthChanged
from app.events.bus import EventBus


class ToolRegistry:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._permissions = PermissionRegistry()
        self._event_bus = event_bus
        self._category_index: Dict[ToolCategory, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, tool: ToolDefinition) -> None:
        if tool.id in self._tools:
            logger.warning(f"Tool '{tool.id}' already registered, updating")
            self._deindex_tool(self._tools[tool.id])
        self._tools[tool.id] = tool
        self._permissions.register(tool.id, tool.permission_level)
        self._index_tool(tool)
        self._publish(ToolRegistered(
            tool_id=tool.id,
            name=tool.name,
            category=tool.category.value,
            version=tool.version,
            metadata={
                "description": tool.description,
                "supports_streaming": tool.supports_streaming,
                "supports_cancellation": tool.supports_cancellation,
                "supports_parallel_execution": tool.supports_parallel_execution,
            },
        ))
        logger.info(f"Tool '{tool.id}' ({tool.name}) registered")

    def remove(self, tool_id: str, reason: str = "") -> Optional[ToolDefinition]:
        tool = self._tools.pop(tool_id, None)
        if tool is None:
            return None
        self._permissions.remove(tool_id)
        self._deindex_tool(tool)
        self._publish(ToolRemoved(tool_id=tool_id, name=tool.name, reason=reason))
        logger.info(f"Tool '{tool_id}' removed: {reason}")
        return tool

    # ── Discovery ─────────────────────────────────────────────────────────

    def get(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)

    def get_metadata(self, tool_id: str) -> Optional[ToolMetadata]:
        tool = self._tools.get(tool_id)
        if tool is None:
            return None
        return ToolMetadata.from_definition(tool)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def list_metadata(self) -> List[ToolMetadata]:
        return [ToolMetadata.from_definition(t) for t in self._tools.values()]

    def search_by_name(self, query: str) -> List[ToolDefinition]:
        q = query.lower()
        return [t for t in self._tools.values() if q in t.name.lower()]

    def search_by_description(self, query: str) -> List[ToolDefinition]:
        q = query.lower()
        return [t for t in self._tools.values() if q in t.description.lower()]

    def search_by_capability(self, query: str) -> List[ToolDefinition]:
        q = query.lower()
        return [
            t for t in self._tools.values()
            if q in t.name.lower() or q in t.description.lower()
        ]

    def get_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        ids = self._category_index.get(category, set())
        return [self._tools[tid] for tid in ids if tid in self._tools]

    def search_by_tags(self, tags: List[str]) -> List[ToolDefinition]:
        if not tags:
            return []
        matching: Optional[Set[str]] = None
        for tag in tags:
            t = tag.lower()
            ids = self._tag_index.get(t, set())
            if matching is None:
                matching = set(ids)
            else:
                matching &= ids
        return [self._tools[tid] for tid in (matching or set()) if tid in self._tools]

    def count(self) -> int:
        return len(self._tools)

    # ── Health ────────────────────────────────────────────────────────────

    def get_tool_health(self, tool_id: str) -> Optional[ToolHealth]:
        tool = self._tools.get(tool_id)
        if tool is None:
            return None
        return tool.health

    def update_tool_health(self, tool_id: str, health: ToolHealth) -> bool:
        tool = self._tools.get(tool_id)
        if tool is None:
            return False
        old_status = tool.health.status
        tool.health = health
        if old_status != health.status:
            self._publish(ToolHealthChanged(
                tool_id=tool_id,
                name=tool.name,
                status=health.status,
                message=health.message,
            ))
        return True

    def registry_health(self) -> ToolRegistryHealth:
        total = len(self._tools)
        healthy = sum(
            1 for t in self._tools.values()
            if t.health.status == "healthy"
        )
        unavailable = sum(
            1 for t in self._tools.values()
            if t.health.status == "error" or t.health.status == "unavailable"
        )
        return ToolRegistryHealth(
            status="healthy" if unavailable == 0 else "degraded" if unavailable < total else "unavailable",
            registered_tools=total,
            healthy_tools=healthy,
            unavailable_tools=unavailable,
            permission_registry_size=self._permissions.count,
            details={
                "categories": str(len(self._category_index)),
                "tags": str(len(self._tag_index)),
            },
        )

    # ── Dependency Lookup ─────────────────────────────────────────────────

    def get_dependencies(self, tool_id: str) -> List[ToolDependency]:
        tool = self._tools.get(tool_id)
        if tool is None:
            return []
        return list(tool.dependencies)

    def get_dependents(self, tool_id: str) -> List[ToolDefinition]:
        return [
            t for t in self._tools.values()
            if any(d.tool_id == tool_id for d in t.dependencies)
        ]

    # ── Permission Lookup ─────────────────────────────────────────────────

    def get_permission(self, tool_id: str) -> Optional[PermissionLevel]:
        return self._permissions.get_permission(tool_id)

    def get_tools_by_permission(self, level: PermissionLevel) -> List[ToolDefinition]:
        ids = self._permissions.get_tools_by_permission(level)
        return [self._tools[tid] for tid in ids if tid in self._tools]

    def check_permission(self, tool_id: str, required: PermissionLevel) -> bool:
        return self._permissions.has_permission(tool_id, required)

    # ── Internal ──────────────────────────────────────────────────────────

    def _index_tool(self, tool: ToolDefinition) -> None:
        self._category_index.setdefault(tool.category, set()).add(tool.id)
        for tag in tool.tags:
            self._tag_index.setdefault(tag.lower(), set()).add(tool.id)

    def _deindex_tool(self, tool: ToolDefinition) -> None:
        cat_set = self._category_index.get(tool.category)
        if cat_set:
            cat_set.discard(tool.id)
            if not cat_set:
                del self._category_index[tool.category]
        for tag in tool.tags:
            tag_set = self._tag_index.get(tag.lower())
            if tag_set:
                tag_set.discard(tool.id)
                if not tag_set:
                    del self._tag_index[tag.lower()]

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
