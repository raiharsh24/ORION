from typing import List, Optional

from app.tools.base import ToolDefinition, ToolHealth, ToolDependency, PermissionLevel
from app.tool_selection.base import ToolSelectionContext


class SelectionRules:
    @staticmethod
    def is_healthy(tool: ToolDefinition) -> bool:
        return tool.health.status in ("healthy", "unknown")

    @staticmethod
    def is_available(tool: ToolDefinition) -> bool:
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
