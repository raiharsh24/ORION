from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class MCPTransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"


class MCPConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPConnectionConfig:
    server_name: str
    transport: MCPTransportType = MCPTransportType.STDIO
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    max_retries: int = 3
    auto_reconnect: bool = True


@dataclass
class MCPToolDef:
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ""


@dataclass
class MCPCallResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    tool_name: str = ""
    duration_ms: float = 0.0


@dataclass
class MCPServerInfo:
    name: str
    version: str = "1.0.0"
    tools_count: int = 0
    status: MCPConnectionStatus = MCPConnectionStatus.DISCONNECTED
    connected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    latency_ms: float = 0.0
