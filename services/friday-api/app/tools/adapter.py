"""
Adapter between the executable BaseTool abstraction and the Universal Tool
Registry's ToolDefinition record.

This module activates the already-existing Universal Tool Registry
(`app.tools.registry.ToolRegistry`) by converting every live `BaseTool`
instance into a `ToolDefinition` and registering it. It does NOT change any
tool implementation.
"""
from typing import Dict, Iterable, List, Optional, Tuple

from loguru import logger

from app.tools.base import (
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolHealth,
)
from app.tools.base_tool import BaseTool
from app.tools.registry import ToolRegistry


# ── Category / permission inference (no tool implementation change) ──────────

def _infer_category(name: str) -> ToolCategory:
    n = (name or "").lower()
    if n.startswith("browser"):
        return ToolCategory.BROWSER
    if n.startswith("filesystem"):
        return ToolCategory.FILESYSTEM
    if n.startswith("terminal"):
        return ToolCategory.TERMINAL
    if "clipboard" in n:
        return ToolCategory.CLIPBOARD
    if n.startswith("desktop") or n in ("open_app",):
        return ToolCategory.DESKTOP
    if n.startswith("knowledge"):
        return ToolCategory.KNOWLEDGE
    if n.startswith("mission"):
        return ToolCategory.MISSION
    if n.startswith("workflow"):
        return ToolCategory.WORKFLOW
    if any(k in n for k in ("screenshot", "ocr", "image", "vision", "screen", "camera")):
        return ToolCategory.OCR
    return ToolCategory.CUSTOM_PLUGINS


# Tools that can affect the host system get a higher permission level so that
# the selection engine filters them out for low-privilege contexts by default.
_ELEVATED_PREFIXES = ("terminal", "filesystem", "desktop", "open_app")


def _infer_permission(name: str) -> PermissionLevel:
    n = (name or "").lower()
    for prefix in _ELEVATED_PREFIXES:
        if n.startswith(prefix):
            return PermissionLevel.ELEVATED
    return PermissionLevel.USER


def build_tool_definition(
    tool: BaseTool,
    *,
    tool_id: Optional[str] = None,
    category: Optional[ToolCategory] = None,
    permission_level: Optional[PermissionLevel] = None,
    tags: Optional[List[str]] = None,
    version: str = "1.0.0",
) -> ToolDefinition:
    """Convert a single BaseTool instance into a ToolDefinition."""
    tid = tool_id or tool.name
    description = tool.description or f"Tool: {tid}"
    inferred_tags = tags if tags is not None else [tid.split(".")[0]] if "." in tid else [tid]
    return ToolDefinition(
        id=tid,
        name=tool.name,
        description=description,
        category=category or _infer_category(tid),
        version=version,
        permission_level=permission_level or _infer_permission(tid),
        health=ToolHealth(status="healthy"),
        tags=inferred_tags,
        enabled=getattr(tool, "_auto_enabled", True),
        parameters=list(getattr(tool, "parameters", [])),
        examples=list(getattr(tool, "examples", [])),
        supports_cancellation=getattr(tool, "supports_cancellation", False),
        supports_streaming=getattr(tool, "supports_streaming", False),
        supports_parallel_execution=getattr(tool, "supports_parallel_execution", False),
    )


def register_tool(
    registry: ToolRegistry,
    tool: BaseTool,
    *,
    tool_id: Optional[str] = None,
    category: Optional[ToolCategory] = None,
    permission_level: Optional[PermissionLevel] = None,
    tags: Optional[List[str]] = None,
) -> ToolDefinition:
    """Build a ToolDefinition from a BaseTool and register it (idempotent)."""
    if not isinstance(tool, BaseTool):
        logger.warning(f"Skipping non-BaseTool instance for id={tool_id}: {type(tool)}")
        raise TypeError("register_tool expects a BaseTool instance")
    definition = build_tool_definition(
        tool,
        tool_id=tool_id,
        category=category,
        permission_level=permission_level,
        tags=tags,
    )
    registry.register(definition)
    return definition


def register_tools(
    registry: ToolRegistry,
    items: Iterable[BaseTool],
    *,
    ids: Optional[Dict[int, str]] = None,
) -> List[ToolDefinition]:
    """Register many BaseTool instances.

    `ids` is an optional mapping from list index -> explicit tool id.
    """
    registered: List[ToolDefinition] = []
    for idx, tool in enumerate(items):
        tid = ids.get(idx) if ids else None
        registered.append(register_tool(registry, tool, tool_id=tid))
    return registered
