import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.mcp_runtime.base import (
    MCPConnectionConfig,
    MCPConnectionStatus,
    MCPTransportType,
)
from app.mcp_runtime.client import MCPClient
from app.mcp_runtime.registry import MCPRegistry
from app.mcp_runtime.adapter import (
    register_mcp_server_tools,
    mcp_tool_to_definition,
    MCPToolWrapper,
)
from app.mcp_providers.filesystem.server import FilesystemMCPServer
from app.mcp_providers.filesystem.permissions import (
    FilesystemPermissionEnforcer,
    PathPermissionError,
)


# =============================================================================
# Unit Tests — Path Permission Enforcer
# =============================================================================


class TestFilesystemPermissionEnforcer:
    def test_allows_path_within_allowed_dir(self):
        e = FilesystemPermissionEnforcer(allowed_directories=["/tmp/test"])
        p = e.resolve("/tmp/test/foo/bar.txt")
        assert str(p) == "/tmp/test/foo/bar.txt"

    def test_allows_allowed_dir_itself(self):
        e = FilesystemPermissionEnforcer(allowed_directories=["/tmp/test"])
        p = e.resolve("/tmp/test")
        assert str(p) == "/tmp/test"

    def test_rejects_path_outside_allowed_dir(self):
        e = FilesystemPermissionEnforcer(allowed_directories=["/tmp/test"])
        with pytest.raises(PathPermissionError, match="Access denied"):
            e.resolve("/etc/passwd")

    def test_rejects_path_outside_with_substring(self):
        e = FilesystemPermissionEnforcer(allowed_directories=["/tmp/test"])
        with pytest.raises(PathPermissionError):
            e.resolve("/tmp/test_evil/foo")

    def test_multiple_allowed_dirs(self):
        e = FilesystemPermissionEnforcer(
            allowed_directories=["/tmp/a", "/tmp/b"]
        )
        assert e.resolve("/tmp/a/foo")
        assert e.resolve("/tmp/b/bar")
        with pytest.raises(PathPermissionError):
            e.resolve("/tmp/c/baz")

    def test_resolves_home_directory(self):
        e = FilesystemPermissionEnforcer(allowed_directories=[os.path.expanduser("~")])
        p = e.resolve("~/test.txt")
        assert str(p).startswith(os.path.expanduser("~"))

    def test_allowed_directories_property(self):
        e = FilesystemPermissionEnforcer(allowed_directories=["/tmp/a"])
        assert "/tmp/a" in e.allowed_directories()[0]


# =============================================================================
# Unit Tests — FilesystemMCPServer (in-process)
# =============================================================================


@pytest.fixture
def tmp_allowed():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def fs_server(tmp_allowed):
    return FilesystemMCPServer(allowed_directory=tmp_allowed)


class TestFilesystemMCPServer:
    def test_initialize(self, fs_server):
        result = fs_server.handle_initialize()
        assert result["serverInfo"]["name"] == "friday-filesystem"
        assert result["protocolVersion"] == "0.1.0"

    def test_list_tools(self, fs_server):
        result = fs_server.handle_list_tools()
        tools = result["tools"]
        names = [t["name"] for t in tools]
        assert "read_file" in names
        assert "write_file" in names
        assert "list_directory" in names
        assert "file_info" in names
        assert "search_files" in names
        assert "delete_file" in names
        assert all("inputSchema" in t for t in tools)

    def test_write_and_read_file(self, fs_server, tmp_allowed):
        path = os.path.join(tmp_allowed, "hello.txt")
        result = fs_server.handle_call_tool({
            "name": "write_file",
            "arguments": {"path": path, "content": "Hello World"},
        })
        assert not result.get("isError")
        assert os.path.exists(path)

        result = fs_server.handle_call_tool({
            "name": "read_file",
            "arguments": {"path": path},
        })
        assert result["content"][0]["text"] == "Hello World"

    def test_list_directory(self, fs_server, tmp_allowed):
        Path(os.path.join(tmp_allowed, "a.txt")).write_text("a")
        Path(os.path.join(tmp_allowed, "b.txt")).write_text("b")
        result = fs_server.handle_call_tool({
            "name": "list_directory",
            "arguments": {"path": tmp_allowed},
        })
        entries = json.loads(result["content"][0]["text"])
        names = [e["name"] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_file_info(self, fs_server, tmp_allowed):
        path = os.path.join(tmp_allowed, "test.txt")
        Path(path).write_text("data")
        result = fs_server.handle_call_tool({
            "name": "file_info",
            "arguments": {"path": path},
        })
        info = json.loads(result["content"][0]["text"])
        assert info["name"] == "test.txt"
        assert info["type"] == "file"
        assert info["size"] == 4

    def test_search_files(self, fs_server, tmp_allowed):
        Path(os.path.join(tmp_allowed, "main.py")).write_text("# python")
        Path(os.path.join(tmp_allowed, "test.py")).write_text("# test")
        Path(os.path.join(tmp_allowed, "readme.md")).write_text("# docs")
        result = fs_server.handle_call_tool({
            "name": "search_files",
            "arguments": {"pattern": "*.py", "root": tmp_allowed},
        })
        matches = json.loads(result["content"][0]["text"])
        assert "main.py" in matches
        assert "test.py" in matches
        assert "readme.md" not in matches

    def test_delete_file(self, fs_server, tmp_allowed):
        path = os.path.join(tmp_allowed, "delete_me.txt")
        Path(path).write_text("bye")
        assert os.path.exists(path)
        result = fs_server.handle_call_tool({
            "name": "delete_file",
            "arguments": {"path": path},
        })
        assert not result.get("isError")
        assert not os.path.exists(path)

    def test_permission_denied_outside_allowed(self, fs_server):
        result = fs_server.handle_call_tool({
            "name": "read_file",
            "arguments": {"path": "/etc/passwd"},
        })
        assert result.get("isError")
        assert "Access denied" in result["content"][0]["text"]

    def test_unknown_tool(self, fs_server):
        result = fs_server.handle_call_tool({
            "name": "nonexistent",
            "arguments": {},
        })
        assert result.get("isError")

    def test_file_not_found(self, fs_server, tmp_allowed):
        path = os.path.join(tmp_allowed, "nonexistent.txt")
        result = fs_server.handle_call_tool({
            "name": "read_file",
            "arguments": {"path": path},
        })
        assert result.get("isError")

    def test_write_create_parent_dirs(self, fs_server, tmp_allowed):
        path = os.path.join(tmp_allowed, "a", "b", "c", "deep.txt")
        result = fs_server.handle_call_tool({
            "name": "write_file",
            "arguments": {"path": path, "content": "nested"},
        })
        assert not result.get("isError")
        assert os.path.exists(path)


# =============================================================================
# Integration Tests — MCP Runtime + Real Filesystem Server (subprocess)
# =============================================================================


@pytest.mark.anyio
class TestMCPFilesystemIntegration:
    @pytest.fixture
    def tmpdir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def server_config(self, tmpdir):
        return MCPConnectionConfig(
            server_name="fs-test",
            transport=MCPTransportType.STDIO,
            command=sys.executable,
            args=[
                "-m",
                "app.mcp_providers.filesystem.server",
                "--allowed-dir",
                tmpdir,
            ],
            timeout_seconds=5.0,
            auto_reconnect=False,
        )

    @pytest.fixture
    async def client(self, server_config):
        client = MCPClient(server_config)
        info = await client.connect()
        assert info.status == MCPConnectionStatus.CONNECTED
        yield client
        await client.disconnect()

    async def test_connect_and_list_tools(self, client):
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "read_file" in names
        assert "write_file" in names
        assert "list_directory" in names
        assert "file_info" in names
        assert "search_files" in names
        assert "delete_file" in names
        assert len(tools) == 6

    async def test_write_and_read_through_mcp(self, client, tmpdir):
        path = os.path.join(tmpdir, "greeting.txt")
        result = await client.call_tool("write_file", {
            "path": path,
            "content": "Hello from MCP",
        })
        assert result.success
        assert "Written" in result.output

        result = await client.call_tool("read_file", {"path": path})
        assert result.success
        assert result.output == "Hello from MCP"

    async def test_list_directory_through_mcp(self, client, tmpdir):
        Path(os.path.join(tmpdir, "alpha.txt")).write_text("a")
        Path(os.path.join(tmpdir, "beta.txt")).write_text("b")

        result = await client.call_tool("list_directory", {"path": tmpdir})
        assert result.success
        entries = json.loads(result.output)
        assert len(entries) == 2

    async def test_search_files_through_mcp(self, client, tmpdir):
        Path(os.path.join(tmpdir, "app.py")).write_text("# app")
        Path(os.path.join(tmpdir, "util.py")).write_text("# util")

        result = await client.call_tool("search_files", {
            "pattern": "*.py",
            "root": tmpdir,
        })
        assert result.success
        matches = json.loads(result.output)
        assert "app.py" in matches
        assert "util.py" in matches

    async def test_delete_through_mcp(self, client, tmpdir):
        path = os.path.join(tmpdir, "temp.txt")
        Path(path).write_text("temp")
        assert os.path.exists(path)

        result = await client.call_tool("delete_file", {"path": path})
        assert result.success
        assert not os.path.exists(path)

    async def test_file_info_through_mcp(self, client, tmpdir):
        path = os.path.join(tmpdir, "info.txt")
        Path(path).write_text("metadata")
        result = await client.call_tool("file_info", {"path": path})
        assert result.success
        info = json.loads(result.output)
        assert info["name"] == "info.txt"
        assert info["size"] == 8

    async def test_permission_denied_through_mcp(self, client):
        result = await client.call_tool("read_file", {"path": "/etc/shadow"})
        assert not result.success
        assert "Access denied" in result.error

    async def test_ping(self, client):
        assert await client.ping()

    async def test_server_info(self, client):
        assert client.server_info.status == MCPConnectionStatus.CONNECTED
        assert client.server_info.name == "friday-filesystem"

    async def test_unknown_method(self, client):
        result = await client.call_tool("nonexistent", {})
        assert not result.success
        assert "Unknown tool" in result.error


# =============================================================================
# Integration Tests — Two-Registry Bridge with Filesystem MCP
# =============================================================================


@pytest.mark.anyio
class TestMCPFilesystemRegistryBridge:
    @pytest.fixture
    def tmpdir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    async def registry_with_server(self, tmpdir):
        from app.tools.registry import ToolRegistry as UniversalRegistry
        from app.friday.tool_registry import ToolRegistry as LegacyRegistry

        universal = UniversalRegistry(event_bus=MagicMock())
        legacy = LegacyRegistry()
        mcp_registry = MCPRegistry()

        config = MCPConnectionConfig(
            server_name="fs-prod",
            transport=MCPTransportType.STDIO,
            command=sys.executable,
            args=[
                "-m",
                "app.mcp_providers.filesystem.server",
                "--allowed-dir",
                tmpdir,
            ],
            timeout_seconds=5.0,
            auto_reconnect=False,
        )

        client = MCPClient(config)
        info = await client.connect()
        assert info.status == MCPConnectionStatus.CONNECTED
        mcp_registry._servers["fs-prod"] = client

        tids = await register_mcp_server_tools(
            mcp_registry=mcp_registry,
            universal_registry=universal,
            legacy_registry=legacy,
            server_name="fs-prod",
        )
        yield {
            "universal": universal,
            "legacy": legacy,
            "mcp_registry": mcp_registry,
            "client": client,
            "tool_ids": tids,
            "tmpdir": tmpdir,
        }

        await client.disconnect()

    async def test_tools_registered_in_both_registries(self, registry_with_server):
        r = registry_with_server
        assert len(r["tool_ids"]) == 6
        for tid in r["tool_ids"]:
            definition = r["universal"].get(tid)
            assert definition is not None, f"{tid} missing from universal registry"
            assert "mcp" in definition.tags
            assert definition.author == "mcp:fs-prod"

            wrapper = r["legacy"].get(tid)
            assert wrapper is not None, f"{tid} missing from legacy registry"
            assert isinstance(wrapper, MCPToolWrapper)

    async def test_tool_metadata_correct(self, registry_with_server):
        r = registry_with_server
        read_def = r["universal"].get("mcp.fs-prod.read_file")
        assert read_def is not None
        assert read_def.category is not None
        assert read_def.permission_level is not None

        write_def = r["universal"].get("mcp.fs-prod.write_file")
        assert write_def is not None

        delete_def = r["universal"].get("mcp.fs-prod.delete_file")
        assert delete_def is not None

    async def test_mcp_tool_is_selectable(self, registry_with_server):
        from app.tool_selection.selector import ToolSelectionEngine
        from app.tool_selection.base import ToolSelectionContext, SelectedTool
        from app.tools.base import PermissionLevel

        r = registry_with_server
        selector = ToolSelectionEngine(
            tool_registry=r["universal"],
            event_bus=MagicMock(),
        )
        context = ToolSelectionContext(
            user_permission_level=PermissionLevel.ELEVATED,
        )
        result = await selector.select(context)
        assert len(result.selected_tools) > 0, "At least one tool should be selected"
        assert result.confidence > 0
        # Verify each registered tool exists and can be individually verified
        for tid in r["tool_ids"]:
            tool_def = r["universal"].get(tid)
            assert tool_def is not None, f"{tid} must be registered"
            # Tool should pass selection filters
            from app.tool_selection.rules import SelectionRules
            assert SelectionRules.is_available(tool_def), f"{tid} should be available"

    async def test_mcp_tool_execution_through_engine(self, registry_with_server):
        from app.tool_execution.executor import ToolExecutionEngine
        from app.tool_selection.base import SelectedTool, ToolSelectionResult

        r = registry_with_server

        executor = ToolExecutionEngine(
            legacy_tool_registry=r["legacy"],
            universal_tool_registry=r["universal"],
            event_bus=MagicMock(),
        )

        path = os.path.join(r["tmpdir"], "engine_test.txt")
        write_id = "mcp.fs-prod.write_file"
        write_def = r["universal"].get(write_id)
        selected = SelectedTool(tool=write_def, score=1.0, selection_reason="test")
        sel_result = ToolSelectionResult(
            selected_tools=[selected],
            confidence=1.0,
            selection_latency_ms=1.0,
        )
        exec_result = await executor.execute(sel_result, {
            write_id: {"path": path, "content": "engine works"},
        })
        assert exec_result is not None
        assert len(exec_result.results) == 1
        assert exec_result.results[0].success
        assert os.path.exists(path)
        assert Path(path).read_text() == "engine works"

    async def test_mcp_tool_selection_with_category_filter(self, registry_with_server):
        from app.tool_selection.selector import ToolSelectionEngine
        from app.tool_selection.base import ToolSelectionContext
        from app.tools.base import PermissionLevel

        r = registry_with_server
        selector = ToolSelectionEngine(
            tool_registry=r["universal"],
            event_bus=MagicMock(),
        )

        ctx = ToolSelectionContext(
            required_categories=["filesystem"],
            user_permission_level=PermissionLevel.ELEVATED,
        )
        result = await selector.select(ctx)
        assert len(result.selected_tools) > 0
        for st in result.selected_tools:
            assert st.tool.category.value == "filesystem", (
                f"{st.tool.id} should match 'filesystem' category, got {st.tool.category.value}"
            )

    async def test_fs_provider_config_helper(self):
        from app.mcp_providers.filesystem import filesystem_server_config
        config = filesystem_server_config(
            server_name="myfs",
            allowed_directory="/home/user/projects",
        )
        assert config.server_name == "myfs"
        assert "allowed-dir" in str(config.args)
        assert "/home/user/projects" in str(config.args)
        assert config.transport == MCPTransportType.STDIO
