import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

from app.mcp_runtime.base import (
    MCPConnectionConfig, MCPConnectionStatus, MCPTransportType,
    MCPToolDef, MCPCallResult, MCPServerInfo,
)
from app.mcp_runtime.client import MCPClient
from app.mcp_runtime.registry import MCPRegistry
from app.mcp_runtime.adapter import (
    MCPToolWrapper,
    mcp_tool_to_definition,
    infer_category,
    infer_permission,
    register_mcp_server_tools,
)
from app.mcp_runtime.events import (
    MCPServerConnected, MCPServerDisconnected,
    MCPToolDiscovered, MCPToolCallCompleted,
)
from app.mcp_runtime.integration import create_mcp_runtime, shutdown_mcp_runtime
from app.mcp_runtime.transport import StdioTransport, SSETransport, MCPTransport

from app.tools.base import ToolCategory, PermissionLevel, ToolDefinition, ToolHealth
from app.tools.registry import ToolRegistry
from app.tools.base_tool import BaseTool
from app.events.bus import EventBus
from app.kernel.config import MCPConfig, MCPServerEntry, FridayKernelConfig

# =============================================================================
# Data Model Tests
# =============================================================================

class TestMCPDataModels:
    def test_mcp_connection_config_defaults(self):
        c = MCPConnectionConfig(server_name="test", command="server")
        assert c.server_name == "test"
        assert c.transport == MCPTransportType.STDIO
        assert c.timeout_seconds == 30.0

    def test_mcp_config_defaults(self):
        cfg = MCPConfig()
        assert cfg.servers == []

    def test_mcp_server_entry_defaults(self):
        entry = MCPServerEntry(server_name="tools", command="mcp-server")
        assert entry.server_name == "tools"
        assert entry.transport == "stdio"
        assert entry.args == []
        assert entry.timeout_seconds == 30.0
        assert entry.auto_reconnect

    def test_mcp_server_entry_url_transport(self):
        entry = MCPServerEntry(server_name="remote", transport="sse", url="http://localhost:8080/mcp")
        assert entry.transport == "sse"
        assert entry.url == "http://localhost:8080/mcp"

    def test_friday_kernel_config_has_mcp(self):
        cfg = FridayKernelConfig.load_defaults()
        assert hasattr(cfg, "mcp")
        assert isinstance(cfg.mcp, MCPConfig)
        assert cfg.mcp.servers == []

    def test_friday_kernel_config_with_mcp_servers(self):
        cfg = FridayKernelConfig(
            mcp=MCPConfig(
                servers=[
                    MCPServerEntry(server_name="fs", command="mcp-filesystem", args=["--dir", "/tmp"]),
                    MCPServerEntry(server_name="web", transport="sse", url="http://localhost:9090/sse"),
                ]
            )
        )
        assert len(cfg.mcp.servers) == 2
        assert cfg.mcp.servers[0].server_name == "fs"
        assert cfg.mcp.servers[0].command == "mcp-filesystem"
        assert cfg.mcp.servers[1].transport == "sse"
        assert cfg.mcp.servers[1].url == "http://localhost:9090/sse"

    def test_mcp_tool_def_creation(self):
        t = MCPToolDef(name="search", description="Search tool", input_schema={"type": "object"})
        assert t.name == "search"
        assert t.description == "Search tool"
        assert t.input_schema == {"type": "object"}

    def test_mcp_call_result_success(self):
        r = MCPCallResult(success=True, output="result", tool_name="test", duration_ms=10.0)
        assert r.success
        assert r.output == "result"

    def test_mcp_call_result_failure(self):
        r = MCPCallResult(success=False, error="fail", tool_name="test", duration_ms=5.0)
        assert not r.success
        assert r.error == "fail"

    def test_mcp_server_info_defaults(self):
        i = MCPServerInfo(name="test")
        assert i.name == "test"
        assert i.status == MCPConnectionStatus.DISCONNECTED
        assert i.tools_count == 0

# =============================================================================
# MCPClient Tests
# =============================================================================

class FakeTransport(MCPTransport):
    def __init__(self) -> None:
        self._sent: list = []
        self._to_read: list = []
        self._response_queue: list = []
        self._connected = False

    def add_response(self, result: dict) -> None:
        self._response_queue.append(result)

    async def connect(self) -> None:
        self._connected = True

    async def send_message(self, message: dict) -> None:
        self._sent.append(message)
        req_id = message.get("id")
        if self._response_queue:
            result = self._response_queue.pop(0)
            self._to_read.append({"id": req_id, **result})

    async def read_message(self) -> dict:
        if self._to_read:
            return self._to_read.pop(0)
        await asyncio.sleep(0.01)
        return None

    async def close(self) -> None:
        self._connected = False


@pytest.mark.anyio
class TestMCPClient:
    @pytest.fixture
    def config(self):
        return MCPConnectionConfig(
            server_name="test-server",
            command="test",
            args=[],
        )

    @pytest.fixture
    def transport(self):
        return FakeTransport()

    @pytest.fixture
    def client(self, config, transport):
        c = MCPClient(config)
        c._transport = transport
        return c

    async def test_connect_success(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test-server", "version": "1.0.0"}},
        })
        info = await client.connect()
        assert info.name == "test-server"
        assert info.status == MCPConnectionStatus.CONNECTED

    async def test_connect_with_real_send(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test-server", "version": "1.0.0"}},
        })
        await client.connect()
        assert len(transport._sent) == 1
        assert transport._sent[0]["method"] == "initialize"

    async def test_list_tools(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test", "version": "1.0"}},
        })
        await client.connect()
        transport.add_response({
            "result": {
                "tools": [
                    {"name": "search", "description": "Search web", "inputSchema": {}},
                    {"name": "fetch", "description": "Fetch URL", "inputSchema": {}},
                ],
            },
        })
        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[1].name == "fetch"

    async def test_call_tool_success(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test", "version": "1.0"}},
        })
        await client.connect()
        transport.add_response({
            "result": {"content": [{"type": "text", "text": "hello world"}]},
        })
        result = await client.call_tool("search", {"q": "test"})
        assert result.success
        assert result.output == "hello world"
        assert result.duration_ms > 0

    async def test_call_tool_error(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test", "version": "1.0"}},
        })
        await client.connect()
        transport.add_response({
            "result": {"content": [{"type": "text", "text": "error occurred"}], "isError": True},
        })
        result = await client.call_tool("search", {"q": "test"})
        assert not result.success
        assert result.error == "error occurred"

    async def test_ping_success(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test", "version": "1.0"}},
        })
        await client.connect()
        transport.add_response({"result": {}})
        ok = await client.ping()
        assert ok

    async def test_status_initially_disconnected(self, config):
        c = MCPClient(config)
        assert c.status == MCPConnectionStatus.DISCONNECTED

    async def test_server_info_before_connect(self, config):
        c = MCPClient(config)
        assert c.server_info is None

    async def test_server_name(self, config):
        c = MCPClient(config)
        assert c.server_name == "test-server"

    async def test_disconnect(self, client, transport):
        transport.add_response({
            "result": {"serverInfo": {"name": "test", "version": "1.0"}},
        })
        await client.connect()
        assert client.status == MCPConnectionStatus.CONNECTED
        await client.disconnect()
        assert client.status == MCPConnectionStatus.DISCONNECTED

    async def test_transport_failure(self, config):
        c = MCPClient(config)
        c._transport = StdioTransport(command="nonexistent-binary", args=[])
        info = await c.connect()
        assert info.status == MCPConnectionStatus.ERROR

# =============================================================================
# MCPRegistry Tests
# =============================================================================

@pytest.mark.anyio
class TestMCPRegistry:
    @pytest.fixture
    def registry(self):
        return MCPRegistry()

    @pytest.fixture
    def server_config(self):
        return MCPConnectionConfig(
            server_name="test-server",
            command="/bin/echo",
            args=[],
        )

    async def test_register_server_config(self, registry: MCPRegistry, server_config):
        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="tool1"),
            MCPToolDef(name="tool2"),
        ])
        config = MCPConnectionConfig(server_name="mock-server", command="test")
        tools = await registry._register_server_with_client(config, mock_client)
        assert len(tools) == 2

    async def test_duplicate_server_raises(self, registry: MCPRegistry, server_config):
        registry._servers["test-server"] = MagicMock()
        with pytest.raises(ValueError, match="already registered"):
            await registry.register_server_config(server_config)

    async def test_disconnect_server(self, registry: MCPRegistry):
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        mock_client.server_info = MCPServerInfo(name="test", status=MCPConnectionStatus.CONNECTED)
        registry._servers["test"] = mock_client
        await registry.disconnect_server("test")
        assert "test" not in registry._servers
        mock_client.disconnect.assert_awaited_once()

    async def test_get_server(self, registry: MCPRegistry):
        mock_client = MagicMock()
        registry._servers["test"] = mock_client
        assert registry.get_server("test") is mock_client
        assert registry.get_server("nonexistent") is None

    async def test_get_server_info(self, registry: MCPRegistry):
        mock_client = MagicMock()
        info = MCPServerInfo(name="test", status=MCPConnectionStatus.CONNECTED)
        mock_client.server_info = info
        registry._servers["test"] = mock_client
        assert registry.get_server_info("test") is info
        assert registry.get_server_info("nonexistent") is None

    async def test_list_servers(self, registry: MCPRegistry):
        for i in range(3):
            m = MagicMock()
            m.server_info = MCPServerInfo(name=f"s{i}")
            registry._servers[f"s{i}"] = m
        servers = registry.list_servers()
        assert len(servers) == 3

    async def test_call_tool_success(self, registry: MCPRegistry):
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(
            return_value=MCPCallResult(success=True, output="ok", tool_name="t", duration_ms=5.0)
        )
        registry._servers["test"] = mock_client
        result = await registry.call_tool("test", "t", {})
        assert result.success
        assert result.output == "ok"

    async def test_call_tool_server_not_found(self, registry: MCPRegistry):
        result = await registry.call_tool("nonexistent", "t", {})
        assert not result.success
        assert "not found" in result.error

    async def test_ping_server(self, registry: MCPRegistry):
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)
        registry._servers["test"] = mock_client
        assert await registry.ping_server("test") is True
        assert await registry.ping_server("nonexistent") is False

    async def test_disconnect_all(self, registry: MCPRegistry):
        for i in range(3):
            m = MagicMock()
            m.disconnect = AsyncMock()
            registry._servers[f"s{i}"] = m
        await registry.disconnect_all()
        assert len(registry._servers) == 0

    async def test_get_status_empty(self, registry: MCPRegistry):
        status = registry.get_status()
        assert status["total_servers"] == 0
        assert status["healthy_servers"] == 0

    async def test_on_tool_discovered_callback(self, registry: MCPRegistry):
        calls = []
        async def cb(server: str, tool: MCPToolDef):
            calls.append((server, tool.name))
        registry.on_tool_discovered(cb)
        # Register a server with tools
        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="tool1"),
            MCPToolDef(name="tool2"),
        ])
        mock_client.server_info = MCPServerInfo(name="test", status=MCPConnectionStatus.CONNECTED)
        config = MCPConnectionConfig(server_name="test-server", command="test")
        tools = await registry._register_server_with_client(config, mock_client)
        assert len(calls) == 2
        assert calls[0] == ("test-server", "tool1")

# =============================================================================
# Adapter Tests
# =============================================================================

class TestMCPAdapter:
    def test_infer_category_filesystem(self):
        assert infer_category("file_read") == ToolCategory.FILESYSTEM
        assert infer_category("write_file") == ToolCategory.FILESYSTEM

    def test_infer_category_browser(self):
        assert infer_category("web_search") == ToolCategory.BROWSER
        assert infer_category("http_get") == ToolCategory.BROWSER

    def test_infer_category_git(self):
        assert infer_category("git_commit") == ToolCategory.GIT
        assert infer_category("git_push") == ToolCategory.GIT

    def test_infer_category_docker(self):
        assert infer_category("docker_run") == ToolCategory.DOCKER

    def test_infer_category_terminal(self):
        assert infer_category("bash_exec") == ToolCategory.TERMINAL
        assert infer_category("shell_run") == ToolCategory.TERMINAL

    def test_infer_category_default(self):
        assert infer_category("custom_tool") == ToolCategory.CUSTOM_PLUGINS

    def test_infer_permission_elevated(self):
        assert infer_permission("terminal_exec") == PermissionLevel.ELEVATED
        assert infer_permission("docker_run") == PermissionLevel.ELEVATED
        assert infer_permission("file_delete") == PermissionLevel.ELEVATED

    def test_infer_permission_user(self):
        assert infer_permission("web_search") == PermissionLevel.USER
        assert infer_permission("read_file") == PermissionLevel.USER

    def test_mcp_tool_to_definition(self):
        mcp_tool = MCPToolDef(
            name="web_search",
            description="Search the web",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        definition = mcp_tool_to_definition(mcp_tool, server_name="serp")
        assert definition.id == "mcp.serp.web_search"
        assert definition.name == "web_search"
        assert definition.category == ToolCategory.BROWSER
        assert definition.author == "mcp:serp"
        assert "mcp" in definition.tags
        assert "serp" in definition.tags

    def test_mcp_tool_to_definition_without_server(self):
        mcp_tool = MCPToolDef(name="custom_tool", description="A tool")
        definition = mcp_tool_to_definition(mcp_tool)
        assert definition.id.startswith("mcp.")
        assert definition.category == ToolCategory.CUSTOM_PLUGINS

    def test_mcp_tool_wrapper_properties(self):
        mcp_tool = MCPToolDef(name="test_tool", description="A test tool")
        registry = MagicMock()
        wrapper = MCPToolWrapper(mcp_tool, registry, server_name="test-server")
        assert wrapper.name == "mcp.test-server.test_tool"
        assert "test_tool" in wrapper.description
        assert wrapper.get_mcp_tool() is mcp_tool
        assert wrapper.get_server_name() == "test-server"

    @pytest.mark.anyio
    async def test_mcp_tool_wrapper_execute_success(self):
        mcp_tool = MCPToolDef(name="search", description="Search")
        registry = MagicMock()
        registry.call_tool = AsyncMock(
            return_value=MCPCallResult(success=True, output="results", tool_name="search", duration_ms=10)
        )
        wrapper = MCPToolWrapper(mcp_tool, registry, server_name="server")
        result = await wrapper.execute(q="test")
        assert result == "results"
        registry.call_tool.assert_awaited_once_with("server", "search", {"q": "test"})

    @pytest.mark.anyio
    async def test_mcp_tool_wrapper_execute_failure(self):
        mcp_tool = MCPToolDef(name="search", description="Search")
        registry = MagicMock()
        registry.call_tool = AsyncMock(
            return_value=MCPCallResult(success=False, error="fail", tool_name="search", duration_ms=5)
        )
        wrapper = MCPToolWrapper(mcp_tool, registry, server_name="server")
        with pytest.raises(RuntimeError, match="fail"):
            await wrapper.execute(q="test")

    @pytest.mark.anyio
    async def test_register_mcp_server_tools(self):
        mcp_registry = MCPRegistry()
        universal_registry = ToolRegistry(event_bus=MagicMock())
        legacy_registry = MagicMock()
        legacy_registry.register = MagicMock()

        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="search", description="Search web", input_schema={}),
            MCPToolDef(name="fetch", description="Fetch URL", input_schema={}),
        ])
        mock_client.server_info = MCPServerInfo(name="test", status=MCPConnectionStatus.CONNECTED)
        mcp_registry._servers["test-server"] = mock_client

        tool_ids = await register_mcp_server_tools(
            mcp_registry, universal_registry, legacy_registry, "test-server",
        )
        assert len(tool_ids) == 2
        assert tool_ids[0] == "mcp.test-server.search"
        assert tool_ids[1] == "mcp.test-server.fetch"
        assert universal_registry.get("mcp.test-server.search") is not None
        assert legacy_registry.register.call_count == 2

    @pytest.mark.anyio
    async def test_register_mcp_server_tools_server_not_found(self):
        mcp_registry = MCPRegistry()
        universal_registry = ToolRegistry(event_bus=MagicMock())
        legacy_registry = MagicMock()
        tool_ids = await register_mcp_server_tools(
            mcp_registry, universal_registry, legacy_registry, "nonexistent",
        )
        assert tool_ids == []

# =============================================================================
# Events Tests
# =============================================================================

class TestMCPEvents:
    def test_mcp_server_connected_event(self):
        e = MCPServerConnected("server1", "1.0", 3)
        assert e.topic == "MCPServerConnected"
        assert e.data["server_name"] == "server1"
        assert e.data["tools_count"] == 3

    def test_mcp_server_disconnected_event(self):
        e = MCPServerDisconnected("server1", "connection lost")
        assert e.topic == "MCPServerDisconnected"
        assert e.data["error"] == "connection lost"

    def test_mcp_tool_discovered_event(self):
        e = MCPToolDiscovered("server1", "search")
        assert e.topic == "MCPToolDiscovered"
        assert e.data["tool_name"] == "search"

    def test_mcp_tool_call_completed_event(self):
        e = MCPToolCallCompleted("server1", "search", True, 12.5)
        assert e.topic == "MCPToolCallCompleted"
        assert e.data["success"]
        assert e.data["duration_ms"] == 12.5

# =============================================================================
# Integration Tests (EventBus)
# =============================================================================

@pytest.mark.anyio
class TestMCPIntegration:
    async def test_create_mcp_runtime(self):
        event_bus = EventBus()
        registry = await create_mcp_runtime(event_bus=event_bus)
        assert isinstance(registry, MCPRegistry)
        status = registry.get_status()
        assert status["total_servers"] == 0

    async def test_create_mcp_runtime_without_event_bus(self):
        registry = await create_mcp_runtime(event_bus=None)
        assert isinstance(registry, MCPRegistry)

    async def test_shutdown_mcp_runtime(self):
        registry = await create_mcp_runtime(event_bus=None)
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        registry._servers["test"] = mock_client
        await shutdown_mcp_runtime(registry)
        assert len(registry._servers) == 0

    async def test_mcp_tool_in_universal_registry(self):
        from app.tools.registry import ToolRegistry
        universal_registry = ToolRegistry(event_bus=MagicMock())
        mcp_tool = MCPToolDef(name="search", description="Search web", input_schema={})
        definition = mcp_tool_to_definition(mcp_tool, server_name="server")
        universal_registry.register(definition)
        retrieved = universal_registry.get(definition.id)
        assert retrieved is not None
        assert retrieved.id == definition.id
        assert retrieved.name == "search"
        assert "mcp" in retrieved.tags

    async def test_mcp_tool_selection_compatible(self):
        from app.tools.registry import ToolRegistry
        from app.tool_selection.selector import ToolSelectionEngine
        from app.tool_selection.base import ToolSelectionContext
        from app.tools.base import ToolCategory

        universal_registry = ToolRegistry(event_bus=MagicMock())
        mcp_tool = MCPToolDef(
            name="web_search",
            description="Search the web",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        definition = mcp_tool_to_definition(mcp_tool, server_name="serp")
        universal_registry.register(definition)

        selector = ToolSelectionEngine(tool_registry=universal_registry, event_bus=MagicMock())
        context = ToolSelectionContext(required_capabilities=["web_search"])

        result = await selector.select(context)
        assert len(result.selected_tools) >= 0

    async def test_mcp_event_publish_and_receive(self):
        event_bus = EventBus()
        received = []
        event_bus.subscribe("MCPServerConnected", lambda e: received.append(e))
        event_bus.publish_background(MCPServerConnected("test-server", "1.0", 2))
        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0].data["server_name"] == "test-server"

    async def test_two_registry_bridge(self):
        from app.tools.registry import ToolRegistry as UniversalRegistry
        from app.friday.tool_registry import ToolRegistry as LegacyRegistry
        from app.mcp_runtime.adapter import register_mcp_server_tools

        universal = UniversalRegistry(event_bus=MagicMock())
        legacy = LegacyRegistry()
        mcp_registry = MCPRegistry()

        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="web_search", description="Search web", input_schema={}),
            MCPToolDef(name="file_read", description="Read file", input_schema={}),
        ])
        mock_client.server_info = MCPServerInfo(name="serp", status=MCPConnectionStatus.CONNECTED)
        mcp_registry._servers["serp"] = mock_client

        tids = await register_mcp_server_tools(
            mcp_registry=mcp_registry,
            universal_registry=universal,
            legacy_registry=legacy,
            server_name="serp",
        )
        assert len(tids) == 2
        assert "mcp.serp.web_search" in tids
        assert "mcp.serp.file_read" in tids

        for tid in tids:
            definition = universal.get(tid)
            assert definition is not None, f"{tid} missing from universal registry"
            assert definition.name in ("web_search", "file_read")
            assert "mcp" in definition.tags
            assert definition.author == "mcp:serp"

            wrapper = legacy.get(tid)
            assert wrapper is not None, f"{tid} missing from legacy registry"
            assert wrapper.name == tid
            assert isinstance(wrapper, MCPToolWrapper)

    async def test_integration_factory_with_both_registries(self):
        from app.tools.registry import ToolRegistry as UniversalRegistry
        from app.friday.tool_registry import ToolRegistry as LegacyRegistry

        event_bus = EventBus()
        universal = UniversalRegistry(event_bus=event_bus)
        legacy = LegacyRegistry()

        registry = await create_mcp_runtime(
            event_bus=event_bus,
            universal_registry=universal,
            legacy_registry=legacy,
            server_configs=None,
        )
        assert isinstance(registry, MCPRegistry)
        assert registry.get_status()["total_servers"] == 0

    async def test_integration_factory_with_mock_server(self):
        from app.tools.registry import ToolRegistry as UniversalRegistry
        from app.friday.tool_registry import ToolRegistry as LegacyRegistry

        event_bus = EventBus()
        universal = UniversalRegistry(event_bus=event_bus)
        legacy = LegacyRegistry()

        registry = await create_mcp_runtime(
            event_bus=event_bus,
            universal_registry=universal,
            legacy_registry=legacy,
            server_configs=None,
        )

        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="search", description="Web search", input_schema={"type": "object"}),
        ])
        mock_client.server_info = MCPServerInfo(
            name="mock-server", status=MCPConnectionStatus.CONNECTED,
        )
        mock_client.connect = AsyncMock()

        config = MCPConnectionConfig(server_name="mock-server", command="test")
        tools = await registry._register_server_with_client(config, mock_client)
        assert len(tools) == 1

        from app.mcp_runtime.adapter import register_mcp_server_tools
        tids = await register_mcp_server_tools(
            mcp_registry=registry,
            universal_registry=universal,
            legacy_registry=legacy,
            server_name="mock-server",
        )
        assert len(tids) == 1
        assert universal.get("mcp.mock-server.search") is not None
        assert legacy.get("mcp.mock-server.search") is not None

    async def test_full_selection_execution_pipeline(self):
        from app.tools.registry import ToolRegistry as UniversalRegistry
        from app.friday.tool_registry import ToolRegistry as LegacyRegistry
        from app.tool_selection.selector import ToolSelectionEngine
        from app.tool_selection.base import ToolSelectionContext
        from app.tool_execution.executor import ToolExecutionEngine

        event_bus = EventBus()
        universal = UniversalRegistry(event_bus=event_bus)
        legacy = LegacyRegistry()
        mcp_registry = MCPRegistry()

        mock_client = MagicMock()
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="web_search", description="Search the web", input_schema={}),
        ])
        mock_client.server_info = MCPServerInfo(
            name="search-server", status=MCPConnectionStatus.CONNECTED,
        )
        mock_client.connect = AsyncMock()
        mcp_registry._servers["search-server"] = mock_client

        from app.mcp_runtime.adapter import register_mcp_server_tools
        tids = await register_mcp_server_tools(
            mcp_registry=mcp_registry,
            universal_registry=universal,
            legacy_registry=legacy,
            server_name="search-server",
        )
        assert len(tids) == 1
        tid = tids[0]

        selector = ToolSelectionEngine(tool_registry=universal, event_bus=event_bus)
        context = ToolSelectionContext(required_capabilities=["web_search"])
        selection = await selector.select(context)
        selected_ids = [st.tool.id for st in selection.selected_tools]
        assert tid in selected_ids, f"MCP tool {tid} should be selectable"

        executor = ToolExecutionEngine(
            legacy_tool_registry=legacy,
            universal_tool_registry=universal,
            event_bus=event_bus,
        )
        wrapper = legacy.get(tid)
        assert wrapper is not None
        assert isinstance(wrapper, MCPToolWrapper)

    async def test_mcp_tool_wrapper_executes_through_engine(self):
        from app.tools.registry import ToolRegistry as UniversalRegistry
        from app.friday.tool_registry import ToolRegistry as LegacyRegistry
        from app.tool_execution.executor import ToolExecutionEngine

        event_bus = EventBus()
        universal = UniversalRegistry(event_bus=event_bus)
        legacy = LegacyRegistry()
        mcp_registry = MCPRegistry()

        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(
            return_value=MCPCallResult(success=True, output="search results", tool_name="web_search", duration_ms=5.0),
        )
        mock_client.server_info = MCPServerInfo(
            name="search-server", status=MCPConnectionStatus.CONNECTED,
        )
        mcp_registry._servers["search-server"] = mock_client

        from app.mcp_runtime.adapter import register_mcp_server_tools, mcp_tool_to_definition
        mock_client.list_tools = AsyncMock(return_value=[
            MCPToolDef(name="web_search", description="Search the web", input_schema={}),
        ])
        tids = await register_mcp_server_tools(
            mcp_registry=mcp_registry,
            universal_registry=universal,
            legacy_registry=legacy,
            server_name="search-server",
        )
        assert len(tids) == 1
        tid = tids[0]

        executor = ToolExecutionEngine(
            legacy_tool_registry=legacy,
            universal_tool_registry=universal,
            event_bus=event_bus,
        )
        definition = universal.get(tid)
        from app.tool_selection.base import SelectedTool
        from app.tool_execution.base import ExecutionContext
        from app.tools.base import ToolCategory

        selected = SelectedTool(tool=definition, score=1.0, selection_reason="test")
        from app.tool_selection.base import ToolSelectionResult
        result = ToolSelectionResult(
            selected_tools=[selected],
            confidence=1.0,
            selection_latency_ms=1.0,
        )
        execution_result = await executor.execute(result)
        assert execution_result is not None
        assert len(execution_result.results) > 0
        assert execution_result.results[0].success
        mock_client.call_tool.assert_called_once_with("web_search", {})
