from typing import Any, Dict, List, Optional, Callable, Awaitable
from loguru import logger

from app.mcp_runtime.base import MCPConnectionConfig, MCPToolDef
from app.mcp_runtime.registry import MCPRegistry
from app.mcp_runtime.events import MCPServerConnected, MCPServerDisconnected, MCPToolDiscovered
from app.mcp_runtime.adapter import register_mcp_server_tools


async def create_mcp_runtime(
    event_bus: Optional[Any] = None,
    universal_registry: Optional[Any] = None,
    legacy_registry: Optional[Any] = None,
    server_configs: Optional[List[MCPConnectionConfig]] = None,
) -> MCPRegistry:
    registry = MCPRegistry()

    if event_bus:

        async def _on_connect(server_name: str, version: str, tools_count: int) -> None:
            event_bus.publish_background(
                MCPServerConnected(server_name, version, tools_count)
            )

        async def _on_disconnect(server_name: str, error: str) -> None:
            event_bus.publish_background(
                MCPServerDisconnected(server_name, error)
            )

    if universal_registry and legacy_registry and event_bus:

        async def _on_tool_discovered(server_name: str, tool_def: MCPToolDef) -> None:
            event_bus.publish_background(
                MCPToolDiscovered(server_name, tool_def.name, tool_def.description)
            )

        registry.on_tool_discovered(_on_tool_discovered)

    server_configs = server_configs or []
    for config in server_configs:
        try:
            tools = await registry.register_server_config(config)
            if universal_registry and legacy_registry:
                await register_mcp_server_tools(
                    mcp_registry=registry,
                    universal_registry=universal_registry,
                    legacy_registry=legacy_registry,
                    server_name=config.server_name,
                )
            logger.info(
                f"MCP server '{config.server_name}' connected with {len(tools)} tools"
            )
        except Exception as e:
            logger.warning(
                f"MCP server '{config.server_name}' failed to connect: {e}"
            )

    logger.info(
        f"MCP Runtime created with {len(server_configs)} configured servers"
    )
    return registry


async def shutdown_mcp_runtime(registry: MCPRegistry) -> None:
    await registry.disconnect_all()
    logger.info("MCP Runtime shut down")
