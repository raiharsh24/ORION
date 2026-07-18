# MCP Provider Architecture Guide

## Overview

FRIDAY's MCP (Model Context Protocol) Runtime enables integration with external
tool servers through a standardized JSON-RPC 2.0 protocol over stdio or SSE.
This document describes the architecture and explains how to add new MCP
providers.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  FRIDAY Kernel                   │
│                                                   │
│  ┌────────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Tool       │  │ Tool     │  │ Tool          │ │
│  │ Selection  │  │ Execution│  │ Registry      │ │
│  │ Engine     │  │ Engine   │  │ (Universal)   │ │
│  └─────┬──────┘  └────┬─────┘  └───────┬───────┘ │
│        │              │                │          │
│  ┌─────┴──────────────┴────────────────┴───────┐ │
│  │           MCP Runtime                        │ │
│  │  ┌──────────┐  ┌──────────┐  ┌───────────┐  │ │
│  │  │ MCP      │  │ MCP      │  │ MCP       │  │ │
│  │  │ Client   │  │ Registry │  │ Adapter   │  │ │
│  │  └────┬─────┘  └──────────┘  └───────────┘  │ │
│  └───────┼──────────────────────────────────────┘ │
└──────────┼────────────────────────────────────────┘
           │ stdio / SSE
           │ JSON-RPC 2.0
┌──────────┴────────────────────────────────────────┐
│              MCP Server Process                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  FilesystemMCPServer                         │  │
│  │  ┌──────────── ┌──────────┐ ┌─────────────┐ │  │
│  │  │ read_file  │ write_file│ │ list_dir    │ │  │
│  │  └──────────── └──────────┘ └─────────────┘ │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## How It Works

1. **MCP Server** — A process that implements the MCP protocol (JSON-RPC 2.0
   over stdio). It advertises tools via `tools/list` and executes them via
   `tools/call`.

2. **MCPClient** — Connects to the server subprocess, sends JSON-RPC requests,
   reads responses, and dispatches them to pending futures.

3. **MCPRegistry** — Manages multiple MCP servers. Provides `register_server()`,
   `call_tool()`, and `on_tool_discovered()` callback registration.

4. **MCPToolWrapper** — A `BaseTool` subclass that delegates `execute()` to the
   MCP registry, enabling MCP tools to appear identically to native tools.

5. **Adapter** — `register_mcp_server_tools()` bridges MCP tools into both the
   Universal Tool Registry (for selection/discovery) and Legacy Registry (for
   execution), using the same tool IDs.

## Adding a New MCP Provider

### Step 1: Create the Server Package

Create `app/mcp_providers/<provider>/server.py` with a class that implements
the MCP JSON-RPC protocol:

```
app/mcp_providers/
├── __init__.py                  # provider_config() helper
└── filesystem/
    ├── __init__.py              # filesystem_server_config() helper
    ├── server.py                # FilesystemMCPServer (JSON-RPC handler)
    └── permissions.py           # FilesystemPermissionEnforcer
```

### Step 2: Implement the Server

Your server class must handle these JSON-RPC methods:

| Method | Purpose |
|--------|---------|
| `initialize` | Return `serverInfo` (name, version) and protocol capabilities |
| `ping` | Return `{}` (health check) |
| `tools/list` | Return list of tool definitions with JSON Schema input schemas |
| `tools/call` | Execute a tool by name with provided arguments |

Example server structure:

```python
class MyProviderMCPServer:
    TOOLS = [...]  # List of tool definitions with inputSchema

    def handle_initialize(self, params=None):
        return {"protocolVersion": "0.1.0", "capabilities": {"tools": {}},
                "serverInfo": {"name": "my-provider", "version": "1.0.0"}}

    def handle_list_tools(self, params=None):
        return {"tools": self.TOOLS}

    def handle_call_tool(self, params):
        name = params["name"]
        args = params.get("arguments", {})
        # dispatch to tool_<name>() method
        ...
        return {"content": [{"type": "text", "text": result}]}
```

### Step 3: Add a Config Helper

In `app/mcp_providers/<provider>/__init__.py`, create a factory function that
returns an `MCPConnectionConfig`:

```python
from app.mcp_providers import provider_config
from app.mcp_runtime.base import MCPConnectionConfig

def my_provider_config(server_name="my-provider", **kwargs) -> MCPConnectionConfig:
    return provider_config(
        server_name=server_name,
        command="python",
        args=["-m", "app.mcp_providers.my_provider.server", ...],
        **kwargs,
    )
```

### Step 4: Configure in Kernel Config (Optional)

To auto-connect at boot, add a `MCPServerEntry` to the kernel config:

```python
from app.kernel.config import MCPServerEntry, MCPConfig, FridayKernelConfig

cfg = FridayKernelConfig(
    mcp=MCPConfig(
        servers=[
            MCPServerEntry(
                server_name="my-provider",
                command="python",
                args=["-m", "app.mcp_providers.my_provider.server", "--flag"],
            ),
        ]
    )
)
```

The boot sequence (Step 7s) automatically converts `MCPServerEntry` objects to
`MCPConnectionConfig`, connects each server, and registers tools in both the
Universal Tool Registry and Legacy Registry.

### Step 5: Add Permission Enforcement (If Needed)

For providers that access system resources, create a permission enforcer:

```python
class MyProviderPermissionEnforcer:
    def check(self, action: str, resource: str) -> None:
        if not self._is_allowed(action, resource):
            raise PermissionError(f"Access denied: {action} on {resource}")
```

Integrate it into your server's `handle_call_tool`:

```python
def handle_call_tool(self, params):
    try:
        self._enforcer.check(name, args.get("path", ""))
        ...
    except PermissionError as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}
```

### Step 6: Register Permission Level in Adapter

The `infer_permission()` function in `app/mcp_runtime/adapter.py` automatically
sets permission levels based on tool name patterns. For elevated tools (e.g.,
`delete_file`), ensure the name contains one of the elevated keywords:

```python
elevated = ("terminal", "shell", "exec", "docker", "file.write", "file.delete",
             "git.push", "filesystem.write", "filesystem.delete")
```

Or extend this list if your provider has dangerous operations.

### Step 7: Register Category in Adapter

The `infer_category()` function maps tool names to categories. Ensure your tool
names contain appropriate keywords or extend the function.

## MCP Protocol Reference

### Initialize

```json
// Request
{"jsonrpc": "2.0", "id": "1", "method": "initialize",
 "params": {"protocolVersion": "0.1.0", "capabilities": {},
            "clientInfo": {"name": "friday", "version": "1.0.0"}}}

// Response
{"jsonrpc": "2.0", "id": "1",
 "result": {"protocolVersion": "0.1.0", "capabilities": {"tools": {}},
            "serverInfo": {"name": "my-provider", "version": "1.0.0"}}}
```

### List Tools

```json
// Request
{"jsonrpc": "2.0", "id": "2", "method": "tools/list"}

// Response
{"jsonrpc": "2.0", "id": "2",
 "result": {"tools": [
   {"name": "my_tool", "description": "Does something",
    "inputSchema": {"type": "object", "properties": {
      "param1": {"type": "string", "description": "A parameter"}
    }, "required": ["param1"]}
   }
 ]}}
```

### Call Tool

```json
// Request
{"jsonrpc": "2.0", "id": "3", "method": "tools/call",
 "params": {"name": "my_tool", "arguments": {"param1": "value"}}}

// Response (success)
{"jsonrpc": "2.0", "id": "3",
 "result": {"content": [{"type": "text", "text": "result"}], "isError": false}}

// Response (error)
{"jsonrpc": "2.0", "id": "3",
 "result": {"content": [{"type": "text", "text": "error message"}], "isError": true}}
```

### Ping

```json
// Request
{"jsonrpc": "2.0", "id": "4", "method": "ping"}

// Response
{"jsonrpc": "2.0", "id": "4", "result": {}}
```

## Testing Pattern

Write tests in three layers:

### Layer 1: Unit Tests (in-process server)

```python
def test_my_tool(self):
    server = MyProviderMCPServer(...)
    result = server.handle_call_tool({"name": "my_tool", "arguments": {...}})
    assert not result.get("isError")
```

### Layer 2: Integration Tests (subprocess via MCPClient)

```python
@pytest.mark.anyio
async def test_through_mcp_client(self):
    config = MCPConnectionConfig(server_name="test", ...)
    client = MCPClient(config)
    info = await client.connect()
    assert info.status == MCPConnectionStatus.CONNECTED
    tools = await client.list_tools()
    result = await client.call_tool("my_tool", {...})
    assert result.success
    await client.disconnect()
```

### Layer 3: Registry Bridge Tests

```python
@pytest.mark.anyio
async def test_two_registry_bridge(self):
    universal = ToolRegistry(event_bus=MagicMock())
    legacy = LegacyRegistry()
    mcp_registry = MCPRegistry()
    client = MCPClient(config)
    await client.connect()
    mcp_registry._servers["my-srv"] = client
    tids = await register_mcp_server_tools(
        mcp_registry, universal, legacy, "my-srv")
    assert len(tids) > 0
    assert universal.get(tids[0]) is not None
    assert legacy.get(tids[0]) is not None
```
