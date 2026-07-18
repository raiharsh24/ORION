from typing import Any, Dict, List, Optional
from loguru import logger

from app.tools.base import (
    ToolCategory,
    PermissionLevel,
    ToolDefinition,
    ToolHealth,
)
from app.tools.base_tool import BaseTool
from app.tools.registry import ToolRegistry
from app.friday.tool_registry import ToolRegistry as LegacyToolRegistry

from app.mcp_runtime.base import MCPToolDef
from app.mcp_runtime.registry import MCPRegistry


def infer_category(tool_name: str) -> ToolCategory:
    n = tool_name.lower()
    if any(k in n for k in ("web_search", "internet_search", "http", "web_scrape")):
        return ToolCategory.BROWSER
    if any(k in n for k in ("file", "read", "write", "ls", "dir", "search_file")):
        return ToolCategory.FILESYSTEM
    if any(k in n for k in ("git", "commit", "push", "branch")):
        return ToolCategory.GIT
    if any(k in n for k in ("docker", "container", "image")):
        return ToolCategory.DOCKER
    if any(k in n for k in ("email", "mail", "send")):
        return ToolCategory.EMAIL
    if any(k in n for k in ("terminal", "shell", "bash", "command", "exec")):
        return ToolCategory.TERMINAL
    if any(k in n for k in ("calendar", "meeting", "event")):
        return ToolCategory.CALENDAR
    if any(k in n for k in ("python", "code", "execute")):
        return ToolCategory.PYTHON
    return ToolCategory.CUSTOM_PLUGINS


def infer_permission(tool_name: str) -> PermissionLevel:
    n = tool_name.lower().replace("_", ".")
    elevated = ("terminal", "shell", "exec", "docker", "file.write", "file.delete",
                 "git.push", "filesystem.write", "filesystem.delete")
    for prefix in elevated:
        if n.startswith(prefix) or n == prefix:
            return PermissionLevel.ELEVATED
    n_orig = tool_name.lower()
    for prefix in elevated:
        p_under = prefix.replace(".", "_")
        if n_orig.startswith(p_under) or n_orig == p_under:
            return PermissionLevel.ELEVATED
        p_rev = ".".join(reversed(prefix.split(".")))
        if n.startswith(p_rev) or n == p_rev:
            return PermissionLevel.ELEVATED
    return PermissionLevel.USER


def mcp_tool_to_definition(
    mcp_tool: MCPToolDef,
    *,
    server_name: str = "",
    tool_id: Optional[str] = None,
) -> ToolDefinition:
    tid = tool_id or f"mcp.{server_name}.{mcp_tool.name}" if server_name else f"mcp.{mcp_tool.name}"
    return ToolDefinition(
        id=tid,
        name=mcp_tool.name,
        description=mcp_tool.description or f"MCP tool: {mcp_tool.name} (via {server_name})",
        category=infer_category(mcp_tool.name),
        version="1.0.0",
        author=f"mcp:{server_name}" if server_name else "mcp",
        input_schema=mcp_tool.input_schema,
        permission_level=infer_permission(mcp_tool.name),
        health=ToolHealth(status="healthy"),
        tags=["mcp", server_name] if server_name else ["mcp"],
        supports_cancellation=True,
    )


class MCPToolWrapper(BaseTool):
    def __init__(
        self,
        mcp_tool: MCPToolDef,
        mcp_registry: MCPRegistry,
        *,
        server_name: str = "",
        tool_id: Optional[str] = None,
    ) -> None:
        self._mcp_tool = mcp_tool
        self._registry = mcp_registry
        self._server_name = server_name or mcp_tool.server_name
        self._tool_id = tool_id or f"mcp.{self._server_name}.{mcp_tool.name}"

    @property
    def name(self) -> str:
        return self._tool_id

    @property
    def description(self) -> str:
        desc = self._mcp_tool.description or f"MCP tool: {self._mcp_tool.name}"
        return f"{desc} ({self._tool_id})"

    async def execute(self, **kwargs) -> Any:
        result = await self._registry.call_tool(
            self._server_name,
            self._mcp_tool.name,
            kwargs,
        )
        if result.success:
            return result.output
        raise RuntimeError(result.error or "MCP tool execution failed")

    def get_mcp_tool(self) -> MCPToolDef:
        return self._mcp_tool

    def get_server_name(self) -> str:
        return self._server_name


async def register_mcp_server_tools(
    mcp_registry: MCPRegistry,
    universal_registry: ToolRegistry,
    legacy_registry: LegacyToolRegistry,
    server_name: str,
) -> List[str]:
    client = mcp_registry.get_server(server_name)
    if not client:
        logger.warning(f"MCP server '{server_name}' not found in registry")
        return []

    mcp_tools = await client.list_tools()
    tool_ids: List[str] = []

    for mcp_tool in mcp_tools:
        tid = f"mcp.{server_name}.{mcp_tool.name}"
        tool_ids.append(tid)

        definition = mcp_tool_to_definition(
            mcp_tool, server_name=server_name, tool_id=tid,
        )
        universal_registry.register(definition)

        wrapper = MCPToolWrapper(
            mcp_tool, mcp_registry,
            server_name=server_name, tool_id=tid,
        )
        legacy_registry.register(tid, wrapper)

        logger.debug(f"Registered MCP tool '{tid}' from server '{server_name}'")

    logger.info(f"Registered {len(tool_ids)} MCP tools from server '{server_name}'")
    return tool_ids
