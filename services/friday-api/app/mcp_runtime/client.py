import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from loguru import logger

from app.mcp_runtime.base import (
    MCPConnectionConfig,
    MCPConnectionStatus,
    MCPToolDef,
    MCPCallResult,
    MCPServerInfo,
)
from app.mcp_runtime.transport import MCPTransport, create_transport


class MCPClient:
    def __init__(self, config: MCPConnectionConfig) -> None:
        self._config = config
        self._transport: MCPTransport = create_transport(config)
        self._status = MCPConnectionStatus.DISCONNECTED
        self._server_info: Optional[MCPServerInfo] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None

    @property
    def status(self) -> MCPConnectionStatus:
        return self._status

    @property
    def server_info(self) -> Optional[MCPServerInfo]:
        return self._server_info

    @property
    def server_name(self) -> str:
        return self._config.server_name

    async def connect(self) -> MCPServerInfo:
        self._status = MCPConnectionStatus.CONNECTING
        try:
            await self._transport.connect()
            # Start the read loop BEFORE sending any requests so responses
            # are dispatched to pending futures.
            self._read_task = asyncio.create_task(self._read_loop())
            result = await self._initialize()
            self._server_info = MCPServerInfo(
                name=result.get("serverInfo", {}).get("name", self._config.server_name),
                version=result.get("serverInfo", {}).get("version", "1.0.0"),
                status=MCPConnectionStatus.CONNECTED,
                connected_at=None,
            )
            self._status = MCPConnectionStatus.CONNECTED
            logger.info(f"MCP client connected to '{self._config.server_name}'")
        except Exception as e:
            self._status = MCPConnectionStatus.ERROR
            self._server_info = MCPServerInfo(
                name=self._config.server_name,
                status=MCPConnectionStatus.ERROR,
                last_error=str(e),
            )
            logger.error(f"MCP client failed to connect '{self._config.server_name}': {e}")
        return self._server_info

    async def _initialize(self) -> Dict[str, Any]:
        return await self._send_request("initialize", {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {"name": "friday", "version": "1.0.0"},
        })

    async def list_tools(self) -> List[MCPToolDef]:
        result = await self._send_request("tools/list")
        tools = result.get("tools", [])
        return [
            MCPToolDef(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=self._config.server_name,
            )
            for t in tools
        ]

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> MCPCallResult:
        start = time.time()
        try:
            result = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": args,
            })
            content = result.get("content", [])
            is_error = result.get("isError", False)
            output = self._extract_text(content)
            duration = (time.time() - start) * 1000
            if self._server_info:
                self._server_info.latency_ms = duration
            if is_error:
                return MCPCallResult(
                    success=False, error=output or "Tool returned error",
                    tool_name=tool_name, duration_ms=duration,
                )
            return MCPCallResult(
                success=True, output=output,
                tool_name=tool_name, duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return MCPCallResult(
                success=False, error=str(e),
                tool_name=tool_name, duration_ms=duration,
            )

    async def ping(self) -> bool:
        try:
            await self._send_request("ping", timeout=5.0)
            return True
        except Exception:
            return False

    async def _send_request(
        self, method: str, params: Optional[Dict] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        req_id = str(uuid.uuid4())
        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params:
            message["params"] = params

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = future

        try:
            await self._transport.send_message(message)
            t = timeout or self._config.timeout_seconds
            return await asyncio.wait_for(future, timeout=t)
        finally:
            self._pending_requests.pop(req_id, None)

    async def _read_loop(self) -> None:
        while self._status in (MCPConnectionStatus.CONNECTING, MCPConnectionStatus.CONNECTED):
            try:
                msg = await self._transport.read_message()
                if msg is None:
                    continue
                self._handle_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"MCP read loop error: {e}")
                break
        if self._status != MCPConnectionStatus.ERROR:
            self._status = MCPConnectionStatus.DISCONNECTED

    def _handle_message(self, msg: Dict[str, Any]) -> None:
        msg_id = msg.get("id")
        if msg_id and msg_id in self._pending_requests:
            future = self._pending_requests[msg_id]
            if not future.done():
                if "error" in msg:
                    future.set_exception(RuntimeError(
                        msg["error"].get("message", "MCP error")
                    ))
                else:
                    future.set_result(msg.get("result", {}))

    async def disconnect(self) -> None:
        self._status = MCPConnectionStatus.DISCONNECTED
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        await self._transport.close()

    @staticmethod
    def _extract_text(content: List[Dict]) -> str:
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)


