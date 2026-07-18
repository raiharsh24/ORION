from typing import Dict, List, Optional, Callable, Awaitable
from loguru import logger

from app.mcp_runtime.base import (
    MCPConnectionConfig,
    MCPConnectionStatus,
    MCPToolDef,
    MCPCallResult,
    MCPServerInfo,
)
from app.mcp_runtime.client import MCPClient


class MCPRegistry:
    def __init__(self) -> None:
        self._servers: Dict[str, MCPClient] = {}
        self._callbacks: List[Callable[[str, MCPToolDef], Awaitable[None]]] = []

    def on_tool_discovered(self, callback: Callable[[str, MCPToolDef], Awaitable[None]]) -> None:
        self._callbacks.append(callback)

    async def register_server(self, config: MCPConnectionConfig) -> MCPServerInfo:
        if config.server_name in self._servers:
            raise ValueError(f"MCP server '{config.server_name}' already registered")
        client = MCPClient(config)
        self._servers[config.server_name] = client
        info = await client.connect()
        return info

    async def _register_server_with_client(self, config: MCPConnectionConfig, client: MCPClient) -> List[MCPToolDef]:
        if config.server_name in self._servers:
            raise ValueError(f"MCP server '{config.server_name}' already registered")
        self._servers[config.server_name] = client
        tools = await client.list_tools()
        for tool in tools:
            for cb in self._callbacks:
                try:
                    await cb(config.server_name, tool)
                except Exception as e:
                    logger.debug(f"MCP callback failed: {e}")
        return tools

    async def register_server_config(self, config: MCPConnectionConfig) -> List[MCPToolDef]:
        if config.server_name in self._servers:
            raise ValueError(f"MCP server '{config.server_name}' already registered")
        client = MCPClient(config)
        self._servers[config.server_name] = client
        await client.connect()
        tools = await client.list_tools()
        for tool in tools:
            for cb in self._callbacks:
                try:
                    await cb(config.server_name, tool)
                except Exception as e:
                    logger.debug(f"MCP callback failed: {e}")
        return tools

    async def disconnect_server(self, server_name: str) -> None:
        client = self._servers.pop(server_name, None)
        if client:
            await client.disconnect()

    def get_server(self, server_name: str) -> Optional[MCPClient]:
        return self._servers.get(server_name)

    def get_server_info(self, server_name: str) -> Optional[MCPServerInfo]:
        client = self._servers.get(server_name)
        return client.server_info if client else None

    def list_servers(self) -> List[MCPServerInfo]:
        result = []
        for name, client in self._servers.items():
            info = client.server_info
            if info:
                result.append(info)
        return result

    def list_tools(self) -> List[MCPToolDef]:
        return []

    async def call_tool(self, server_name: str, tool_name: str, args: dict) -> MCPCallResult:
        client = self._servers.get(server_name)
        if not client:
            return MCPCallResult(success=False, error=f"MCP server '{server_name}' not found")
        return await client.call_tool(tool_name, args)

    async def ping_server(self, server_name: str) -> bool:
        client = self._servers.get(server_name)
        if not client:
            return False
        return await client.ping()

    async def disconnect_all(self) -> None:
        for name in list(self._servers.keys()):
            await self.disconnect_server(name)

    def get_status(self) -> dict:
        servers = []
        for name, client in self._servers.items():
            info = client.server_info
            servers.append({
                "name": name,
                "status": client.status.value,
                "tools_count": info.tools_count if info else 0,
                "latency_ms": info.latency_ms if info else 0.0,
            })
        healthy = sum(1 for s in servers if s["status"] == "connected")
        return {
            "total_servers": len(servers),
            "healthy_servers": healthy,
            "servers": servers,
        }
