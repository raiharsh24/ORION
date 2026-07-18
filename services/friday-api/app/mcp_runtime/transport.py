import asyncio
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from app.mcp_runtime.base import MCPConnectionConfig


class MCPTransport(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def read_message(self) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class StdioTransport(MCPTransport):
    def __init__(self, command: str, args: list) -> None:
        self._command = command
        self._args = args
        self._process: Optional[asyncio.subprocess.Process] = None

    async def connect(self) -> None:
        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info(f"MCP stdio transport connected: {self._command}")

    async def send_message(self, message: Dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("Transport not connected")
        line = json.dumps(message) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()

    async def read_message(self) -> Optional[Dict[str, Any]]:
        if not self._process or not self._process.stdout:
            raise RuntimeError("Transport not connected")
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            if not line:
                return None
            return json.loads(line.decode("utf-8"))
        except asyncio.TimeoutError:
            return None

    async def close(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
        logger.info("MCP stdio transport closed")


class SSETransport(MCPTransport):
    def __init__(self, url: str, api_key: Optional[str] = None) -> None:
        self._url = url
        self._api_key = api_key
        self._session = None
        self._reader: Optional[asyncio.StreamReader] = None

    async def connect(self) -> None:
        import httpx
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self._session = httpx.AsyncClient(headers=headers, timeout=30.0)
        logger.info(f"MCP SSE transport connected: {self._url}")

    async def send_message(self, message: Dict[str, Any]) -> None:
        if not self._session:
            raise RuntimeError("Transport not connected")
        resp = await self._session.post(
            self._url,
            json={"messages": [{"type": "jsonrpc", "content": message}]},
        )
        resp.raise_for_status()

    async def read_message(self) -> Optional[Dict[str, Any]]:
        return None

    async def close(self) -> None:
        if self._session:
            await self._session.aclose()
        logger.info("MCP SSE transport closed")


def create_transport(config: "MCPConnectionConfig") -> MCPTransport:
    from app.mcp_runtime.base import MCPTransportType
    if config.transport == MCPTransportType.STDIO:
        return StdioTransport(command=config.command, args=config.args)
    elif config.transport == MCPTransportType.SSE:
        return SSETransport(url=config.url, api_key=config.api_key)
    raise ValueError(f"Unsupported transport: {config.transport}")
