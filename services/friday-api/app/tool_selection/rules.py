import re
from typing import List, Optional, Set

from app.tools.base import ToolDefinition, ToolHealth, ToolDependency, PermissionLevel
from app.tool_selection.base import ToolSelectionContext


class SelectionRules:
    @staticmethod
    def is_healthy(tool: ToolDefinition) -> bool:
        return tool.health.status in ("healthy", "unknown")

    @staticmethod
    def is_available(tool: ToolDefinition) -> bool:
        if not getattr(tool, "enabled", True):
            return False
        return tool.health.status not in ("error", "unavailable")

    @staticmethod
    def has_permission(tool: ToolDefinition, context: ToolSelectionContext) -> bool:
        levels = [PermissionLevel.USER, PermissionLevel.ELEVATED, PermissionLevel.ADMIN, PermissionLevel.SYSTEM]
        user_idx = levels.index(context.user_permission_level)
        tool_idx = levels.index(tool.permission_level)
        return tool_idx <= user_idx

    @staticmethod
    def dependencies_satisfied(tool: ToolDefinition, available_tools: List[str]) -> bool:
        for dep in tool.dependencies:
            if not dep.optional and dep.tool_id not in available_tools:
                return False
        return True

    @staticmethod
    def all_dependencies_satisfied(tool: ToolDefinition, available_tools: List[str]) -> bool:
        return SelectionRules.dependencies_satisfied(tool, available_tools)

    @staticmethod
    def matches_category(tool: ToolDefinition, context: ToolSelectionContext) -> bool:
        if not context.required_categories:
            return True
        return tool.category.value in context.required_categories

    @staticmethod
    def matches_capability(tool: ToolDefinition, context: ToolSelectionContext) -> bool:
        if not context.required_capabilities:
            return True
        q = [c.lower() for c in context.required_capabilities]
        return any(
            qq in tool.name.lower() or qq in tool.description.lower()
            for qq in q
        )

    @staticmethod
    def matches_intent(tool: ToolDefinition, intent_type: str) -> bool:
        intent_lower = intent_type.lower()
        if intent_lower in ("unknown", ""):
            return True
        tool_tags_lower = [t.lower() for t in tool.tags]
        if intent_lower in tool_tags_lower:
            return True
        if intent_lower in tool.category.value:
            return True
        if intent_lower in tool.name.lower():
            return True
        if intent_lower in tool.description.lower():
            return True
        return False

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        return set(re.findall(r"[a-z0-9_]+", text.lower()))

    @staticmethod
    def keyword_overlap(query: str, tool: ToolDefinition) -> float:
        if not query:
            return 0.0
        q_tokens = SelectionRules._tokenize(query)
        if not q_tokens:
            return 0.0
        tool_tokens = (
            SelectionRules._tokenize(tool.name)
            | SelectionRules._tokenize(tool.description)
            | set(t.lower() for t in tool.tags)
            | SelectionRules._tokenize(tool.category.value)
        )
        if not tool_tokens:
            return 0.0
        intersection = q_tokens & tool_tokens
        return round(len(intersection) / len(q_tokens), 4)

    @staticmethod
    def parameter_compatibility(context: ToolSelectionContext, tool: ToolDefinition) -> float:
        if not context.required_capabilities:
            return 0.5
        if not tool.parameters:
            return 0.3
        param_names = {p.name.lower() for p in tool.parameters}
        caps = {c.lower() for c in context.required_capabilities}
        if not param_names or not caps:
            return 0.3
        matches = caps & param_names
        if matches:
            return round(min(1.0, len(matches) / len(caps) + 0.2), 4)
        desc_caps = sum(1 for c in caps if c in tool.description.lower())
        if desc_caps > 0:
            return round(min(1.0, desc_caps / len(caps) * 0.8), 4)
        return 0.2
