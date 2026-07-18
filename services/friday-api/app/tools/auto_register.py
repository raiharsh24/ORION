"""
Auto-registration system for FRIDAY tools.

Provides a `@tool` class decorator that automatically converts a BaseTool
subclass into a ToolDefinition and registers it with the Universal Tool
Registry on kernel boot. Tools declare their metadata (parameters, examples,
categories, permissions) inline.
"""
from typing import Any, Dict, List, Optional, Type

from loguru import logger

from app.tools.base import (
    PermissionLevel,
    ToolCategory,
    ToolDefinition,
    ToolExample,
    ToolHealth,
    ToolParameter,
)
from app.tools.base_tool import BaseTool
from app.tools.registry import ToolRegistry


# ── Category / permission inference ──────────────────────────────────────

_CATEGORY_PREFIX_MAP: Dict[str, ToolCategory] = {
    "browser": ToolCategory.BROWSER,
    "filesystem": ToolCategory.FILESYSTEM,
    "terminal": ToolCategory.TERMINAL,
    "clipboard": ToolCategory.CLIPBOARD,
    "desktop": ToolCategory.DESKTOP,
    "knowledge": ToolCategory.KNOWLEDGE,
    "mission": ToolCategory.MISSION,
    "workflow": ToolCategory.WORKFLOW,
    "memory": ToolCategory.MEMORY,
    "vision": ToolCategory.OCR,
    "screenshot": ToolCategory.OCR,
    "ocr": ToolCategory.OCR,
    "open_app": ToolCategory.DESKTOP,
}

_ELEVATED_PREFIXES = ("terminal", "filesystem", "desktop", "open_app")


def _infer_category(tool_id: str) -> ToolCategory:
    for prefix, cat in _CATEGORY_PREFIX_MAP.items():
        if tool_id.startswith(prefix):
            return cat
    return ToolCategory.CUSTOM_PLUGINS


def _infer_permission(tool_id: str) -> PermissionLevel:
    for prefix in _ELEVATED_PREFIXES:
        if tool_id.startswith(prefix):
            return PermissionLevel.ELEVATED
    return PermissionLevel.USER


# ── The @tool decorator ──────────────────────────────────────────────────


def tool(
    tool_id: Optional[str] = None,
    category: Optional[ToolCategory] = None,
    permission_level: Optional[PermissionLevel] = None,
    tags: Optional[List[str]] = None,
    version: str = "1.0.0",
    enabled: bool = True,
):
    """
    Class decorator that registers a BaseTool subclass with the Universal
    Tool Registry when the tool class is first loaded.

    Usage::

        @tool(tool_id="filesystem.read", category=ToolCategory.FILESYSTEM)
        class MyTool(BaseTool):
            name = "filesystem.read"
            description = "Read files from the workspace"
            ...

    If *tool_id* is omitted the class attribute ``tool_id`` or ``name`` is
    used.  The decorated class keeps working as a normal BaseTool and you
    still instantiate it yourself ``MyTool()``.
    """
    def decorator(cls: Type[BaseTool]) -> Type[BaseTool]:
        tid = tool_id or getattr(cls, "tool_id", None) or getattr(cls, "name", None)
        if not tid:
            raise ValueError(
                f"@{cls.__name__} must provide tool_id or set `name` on the class"
            )

        # Store metadata on the class so the adapter/boot code can use it.
        cls._auto_tool_id = tid
        cls._auto_category = category or _infer_category(tid)
        cls._auto_permission = permission_level or _infer_permission(tid)
        cls._auto_tags = tags or [tid.split(".")[0]] if "." in tid else [tid]
        cls._auto_version = version
        cls._auto_enabled = enabled

        # Build a ToolDefinition stub for registration (no instance needed
        # for metadata). The actual instance is created later during boot.
        # This definition will be completed when register_tool_class is called.
        return cls

    return decorator


def build_definition_from_class(
    cls: Type[BaseTool],
    instance_args: Optional[Dict[str, Any]] = None,
) -> ToolDefinition:
    """
    Build a ToolDefinition from a BaseTool subclass, using metadata stored
    by the ``@tool`` decorator.  If the class was not decorated, metadata
    is inferred from the class attributes.
    """
    tid = getattr(cls, "_auto_tool_id", None) or getattr(cls, "tool_id", None) or getattr(cls, "name", "")
    cat = getattr(cls, "_auto_category", None) or _infer_category(tid)
    perm = getattr(cls, "_auto_permission", None) or _infer_permission(tid)
    tags = getattr(cls, "_auto_tags", None) or [tid.split(".")[0]] if "." in tid else [tid]
    version = getattr(cls, "_auto_version", "1.0.0")
    enabled = getattr(cls, "_auto_enabled", True)

    # Instantiate briefly to read parameters / examples
    try:
        inst = cls(**(instance_args or {}))
    except Exception:
        inst = None

    params: List[ToolParameter] = []
    examples: List[ToolExample] = []
    if inst is not None:
        params = getattr(inst, "parameters", [])
        examples = getattr(inst, "examples", [])
        desc = getattr(inst, "description", f"Tool: {tid}")
    else:
        desc = getattr(cls, "description", f"Tool: {tid}")

    return ToolDefinition(
        id=tid,
        name=getattr(cls, "name", tid),
        description=desc,
        category=cat,
        version=version,
        permission_level=perm,
        health=ToolHealth(status="healthy"),
        tags=tags,
        enabled=enabled,
        parameters=params,
        examples=examples,
        supports_cancellation=getattr(cls, "supports_cancellation", False),
        supports_streaming=getattr(cls, "supports_streaming", False),
        supports_parallel_execution=getattr(cls, "supports_parallel_execution", False),
    )


def register_tool_class(
    registry: ToolRegistry,
    cls: Type[BaseTool],
    instance_args: Optional[Dict[str, Any]] = None,
) -> ToolDefinition:
    """Build and register a ToolDefinition from a BaseTool subclass."""
    definition = build_definition_from_class(cls, instance_args=instance_args)
    registry.register(definition)
    logger.info(f"Auto-registered tool '{definition.id}' from {cls.__name__}")
    return definition


def register_all_tool_classes(
    registry: ToolRegistry,
    classes: List[Type[BaseTool]],
    instance_args_map: Optional[Dict[Type[BaseTool], Dict[str, Any]]] = None,
) -> List[ToolDefinition]:
    """Register multiple BaseTool subclasses at once."""
    registered = []
    for cls in classes:
        args = (instance_args_map or {}).get(cls, {})
        registered.append(register_tool_class(registry, cls, instance_args=args))
    return registered
