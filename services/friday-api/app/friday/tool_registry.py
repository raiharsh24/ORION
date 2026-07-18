"""
DEPRECATED: Legacy ToolRegistry.

This module is retained for backward compatibility. New code should use
``app.tools.registry.ToolRegistry`` (the Universal Tool Registry) instead.

The legacy registry is still populated during boot at
``app.core.dependencies.tool_registry`` and is used as the source of
executable ``BaseTool`` instances by the ``ToolExecutionEngine`` bridge.
"""
import warnings
from typing import Dict, Any, Callable
from loguru import logger
from app.tools.base_tool import BaseTool

warnings.warn(
    "app.friday.tool_registry is deprecated. Use app.tools.registry instead.",
    DeprecationWarning,
    stacklevel=2,
)

class FunctionToolWrapper(BaseTool):
    """
    Wraps standard callable functions to satisfy the BaseTool interface.
    """
    def __init__(self, name: str, func: Callable):
        self._name = name
        self._func = func
        self._desc = func.__doc__ or f"Callable function wrapper for {name}"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._desc

    async def execute(self, **kwargs) -> Any:
        import inspect
        if inspect.iscoroutinefunction(self._func):
            return await self._func(**kwargs)
        else:
            return self._func(**kwargs)

class ToolRegistry:
    """
    DEPRECATED: Legacy ToolRegistry. Use app.tools.registry.ToolRegistry instead.
    """
    def __init__(self) -> None:
        self._registry: Dict[str, BaseTool] = {}

    def register(self, name: str, tool: Any) -> None:
        logger.info(f"Registering tool: '{name}' in ToolRegistry.")
        if isinstance(tool, BaseTool):
            self._registry[name] = tool
        elif callable(tool):
            self._registry[name] = FunctionToolWrapper(name, tool)
        else:
            raise TypeError("Tool must be an instance of BaseTool or a callable.")

    def get(self, name: str) -> BaseTool | None:
        return self._registry.get(name)

    def list_tools(self) -> Dict[str, BaseTool]:
        return self._registry.copy()
