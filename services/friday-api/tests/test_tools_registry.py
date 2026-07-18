import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.tools.base import (
    ToolDefinition, ToolCategory, PermissionLevel, ToolHealth, ToolDependency,
)
from app.tools.metadata import ToolMetadata
from app.tools.permissions import PermissionRegistry
from app.tools.events import ToolRegistered, ToolRemoved, ToolHealthChanged
from app.tools.health import ToolRegistryHealth
from app.tools.registry import ToolRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def registry(event_bus):
    return ToolRegistry(event_bus=event_bus)


def make_tool(tool_id: str = "test_tool", name: str = "Test Tool",
              category: ToolCategory = ToolCategory.FILESYSTEM,
              permission: PermissionLevel = PermissionLevel.USER,
              tags: list = None, dependencies: list = None,
              enabled: bool = True,
              **kwargs) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=f"Description for {name}",
        category=category,
        permission_level=permission,
        tags=tags or [],
        dependencies=dependencies or [],
        enabled=enabled,
        **kwargs,
    )


# ── Tool Model Tests ──────────────────────────────────────────────────────

class TestToolModel:
    def test_tool_definition_defaults(self):
        t = make_tool()
        assert t.id == "test_tool"
        assert t.version == "1.0.0"
        assert t.author == "system"
        assert t.supports_streaming is False
        assert t.supports_cancellation is False
        assert t.supports_parallel_execution is False
        assert t.estimated_cost == 0.0
        assert t.estimated_latency_ms == 0.0
        assert isinstance(t.health, ToolHealth)
        assert t.health.status == "unknown"
        assert isinstance(t.registered_at, datetime)
        assert isinstance(t.updated_at, datetime)

    def test_tool_category_values(self):
        assert ToolCategory.FILESYSTEM.value == "filesystem"
        assert ToolCategory.BROWSER.value == "browser"
        assert ToolCategory.LLM.value == "llm"
        assert ToolCategory.CUSTOM_PLUGINS.value == "custom_plugins"
        categories = [c.value for c in ToolCategory]
        assert len(categories) == 19

    def test_permission_level_values(self):
        assert PermissionLevel.USER.value == "user"
        assert PermissionLevel.ELEVATED.value == "elevated"
        assert PermissionLevel.ADMIN.value == "admin"
        assert PermissionLevel.SYSTEM.value == "system"
        assert len(list(PermissionLevel)) == 4

    def test_tool_health_defaults(self):
        h = ToolHealth()
        assert h.status == "unknown"
        assert h.error_count == 0
        assert h.success_count == 0
        assert h.average_latency_ms == 0.0

    def test_tool_dependency_defaults(self):
        d = ToolDependency(tool_id="dep_tool")
        assert d.tool_id == "dep_tool"
        assert d.optional is False
        assert d.version_requirement is None


# ── Metadata Tests ────────────────────────────────────────────────────────

class TestToolMetadata:
    def test_from_definition(self):
        t = make_tool(tags=["tag1", "tag2"])
        meta = ToolMetadata.from_definition(t)
        assert meta.id == t.id
        assert meta.name == t.name
        assert meta.tags == ["tag1", "tag2"]
        assert meta.category == ToolCategory.FILESYSTEM
        assert meta.permission_level == PermissionLevel.USER

    def test_metadata_independent_copy(self):
        t = make_tool(tags=["original"])
        meta = ToolMetadata.from_definition(t)
        meta.tags.append("new")
        assert "new" not in t.tags


# ── Permission Registry Tests ─────────────────────────────────────────────

class TestPermissionRegistry:
    def test_register_and_get(self):
        pr = PermissionRegistry()
        pr.register("tool_a", PermissionLevel.ADMIN)
        assert pr.get_permission("tool_a") == PermissionLevel.ADMIN
        assert pr.get_permission("nonexistent") is None

    def test_remove(self):
        pr = PermissionRegistry()
        pr.register("tool_a", PermissionLevel.USER)
        pr.remove("tool_a")
        assert pr.get_permission("tool_a") is None

    def test_get_tools_by_permission(self):
        pr = PermissionRegistry()
        pr.register("a", PermissionLevel.USER)
        pr.register("b", PermissionLevel.USER)
        pr.register("c", PermissionLevel.ADMIN)
        user_tools = pr.get_tools_by_permission(PermissionLevel.USER)
        assert user_tools == {"a", "b"}
        admin_tools = pr.get_tools_by_permission(PermissionLevel.ADMIN)
        assert admin_tools == {"c"}

    def test_has_permission(self):
        pr = PermissionRegistry()
        pr.register("user_tool", PermissionLevel.USER)
        pr.register("sys_tool", PermissionLevel.SYSTEM)
        assert pr.has_permission("user_tool", PermissionLevel.USER) is True
        assert pr.has_permission("user_tool", PermissionLevel.ADMIN) is False
        assert pr.has_permission("sys_tool", PermissionLevel.USER) is True
        assert pr.has_permission("nonexistent", PermissionLevel.USER) is False

    def test_clear(self):
        pr = PermissionRegistry()
        pr.register("a", PermissionLevel.USER)
        assert pr.count == 1
        pr.clear()
        assert pr.count == 0


# ── Health Model Tests ────────────────────────────────────────────────────

class TestToolRegistryHealth:
    def test_defaults(self):
        h = ToolRegistryHealth()
        assert h.status == "healthy"
        assert h.registered_tools == 0
        assert h.healthy_tools == 0
        assert h.unavailable_tools == 0
        assert h.total == 0

    def test_to_dict(self):
        h = ToolRegistryHealth(
            status="degraded",
            registered_tools=10,
            healthy_tools=8,
            unavailable_tools=2,
        )
        d = h.to_dict()
        assert d["status"] == "degraded"
        assert d["registered_tools"] == 10
        assert d["healthy_tools"] == 8
        assert d["unavailable_tools"] == 2
        assert "last_checked" in d


# ── Registry Tests ────────────────────────────────────────────────────────

class TestToolRegistry:
    def test_register_tool(self, registry):
        t = make_tool()
        registry.register(t)
        assert registry.count() == 1
        assert registry.get("test_tool") is t

    def test_register_twice_updates(self, registry, event_bus):
        t1 = make_tool(version="1.0.0")
        t2 = make_tool(version="2.0.0")
        registry.register(t1)
        registry.register(t2)
        assert registry.count() == 1
        assert registry.get("test_tool").version == "2.0.0"

    def test_remove_tool(self, registry):
        t = make_tool()
        registry.register(t)
        removed = registry.remove("test_tool", reason="cleanup")
        assert removed is t
        assert registry.count() == 0
        assert registry.get("test_tool") is None

    def test_remove_nonexistent(self, registry):
        assert registry.remove("nonexistent") is None

    def test_register_publishes_event(self, registry, event_bus):
        t = make_tool()
        registry.register(t)
        event_bus.publish.assert_called_once()
        args, _ = event_bus.publish.call_args
        assert isinstance(args[0], ToolRegistered)
        assert args[0].data["tool_id"] == "test_tool"

    def test_remove_publishes_event(self, registry, event_bus):
        t = make_tool()
        registry.register(t)
        event_bus.reset_mock()
        registry.remove("test_tool", reason="cleanup")
        event_bus.publish.assert_called_once()
        args, _ = event_bus.publish.call_args
        assert isinstance(args[0], ToolRemoved)
        assert args[0].data["reason"] == "cleanup"


class TestRegistryDiscovery:
    def test_list_tools(self, registry):
        registry.register(make_tool("a", "Tool A"))
        registry.register(make_tool("b", "Tool B"))
        assert len(registry.list_tools()) == 2

    def test_list_metadata(self, registry):
        registry.register(make_tool("a", "Tool A"))
        metas = registry.list_metadata()
        assert len(metas) == 1
        assert isinstance(metas[0], ToolMetadata)
        assert metas[0].id == "a"

    def test_get_metadata(self, registry):
        registry.register(make_tool("test", "Test Tool"))
        meta = registry.get_metadata("test")
        assert meta is not None
        assert meta.name == "Test Tool"
        assert registry.get_metadata("nonexistent") is None

    def test_search_by_name(self, registry):
        registry.register(make_tool("fs_read", "File Read"))
        registry.register(make_tool("net_get", "Network Get"))
        results = registry.search_by_name("file")
        assert len(results) == 1
        assert results[0].id == "fs_read"
        assert len(registry.search_by_name("nonexistent")) == 0

    def test_search_by_description(self, registry):
        t1 = make_tool("t1", "Tool 1")
        t1.description = "Handles file operations"
        registry.register(t1)
        t2 = make_tool("t2", "Tool 2")
        t2.description = "Network utilities"
        registry.register(t2)
        results = registry.search_by_description("file")
        assert len(results) == 1
        assert results[0].id == "t1"

    def test_search_by_capability(self, registry):
        t1 = make_tool("fs", "File Management")
        t1.description = "File system operations"
        registry.register(t1)
        t2 = make_tool("net", "Network Tools")
        t2.description = "file transfer utilities"
        registry.register(t2)
        results = registry.search_by_capability("file")
        assert len(results) == 2

    def test_get_by_category(self, registry):
        registry.register(make_tool("a", category=ToolCategory.FILESYSTEM))
        registry.register(make_tool("b", category=ToolCategory.BROWSER))
        registry.register(make_tool("c", category=ToolCategory.FILESYSTEM))
        fs_tools = registry.get_by_category(ToolCategory.FILESYSTEM)
        assert len(fs_tools) == 2
        browser_tools = registry.get_by_category(ToolCategory.BROWSER)
        assert len(browser_tools) == 1
        assert len(registry.get_by_category(ToolCategory.LLM)) == 0

    def test_search_by_tags(self, registry):
        registry.register(make_tool("a", tags=["read", "file"]))
        registry.register(make_tool("b", tags=["write", "file"]))
        registry.register(make_tool("c", tags=["read", "network"]))
        both = registry.search_by_tags(["read", "file"])
        assert len(both) == 1
        assert both[0].id == "a"
        read_tools = registry.search_by_tags(["read"])
        assert len(read_tools) == 2
        assert registry.search_by_tags([]) == []


class TestRegistryHealth:
    def test_get_tool_health(self, registry):
        t = make_tool()
        registry.register(t)
        health = registry.get_tool_health("test_tool")
        assert health is t.health
        assert registry.get_tool_health("nonexistent") is None

    def test_update_tool_health(self, registry, event_bus):
        t = make_tool()
        registry.register(t)
        new_health = ToolHealth(status="healthy", success_count=5)
        result = registry.update_tool_health("test_tool", new_health)
        assert result is True
        assert t.health.status == "healthy"
        assert t.health.success_count == 5

    def test_update_tool_health_fires_event_on_change(self, registry, event_bus):
        t = make_tool()
        registry.register(t)
        event_bus.reset_mock()
        new_health = ToolHealth(status="error", message="timeout")
        registry.update_tool_health("test_tool", new_health)
        event_bus.publish.assert_called_once()
        args, _ = event_bus.publish.call_args
        assert isinstance(args[0], ToolHealthChanged)
        assert args[0].data["status"] == "error"

    def test_update_nonexistent_tool_health(self, registry):
        new_health = ToolHealth(status="healthy")
        assert registry.update_tool_health("nonexistent", new_health) is False

    def test_registry_health_empty(self, registry):
        h = registry.registry_health()
        assert h.registered_tools == 0
        assert h.healthy_tools == 0
        assert h.status == "healthy"

    def test_registry_health_with_tools(self, registry):
        t1 = make_tool("a", health=ToolHealth(status="healthy"))
        t2 = make_tool("b", health=ToolHealth(status="error"))
        registry.register(t1)
        registry.register(t2)
        h = registry.registry_health()
        assert h.registered_tools == 2
        assert h.healthy_tools == 1
        assert h.unavailable_tools == 1
        assert h.status == "degraded"

    def test_registry_health_all_unavailable(self, registry):
        registry.register(make_tool("a", health=ToolHealth(status="error")))
        h = registry.registry_health()
        assert h.status == "unavailable"


class TestRegistryDependencies:
    def test_get_dependencies(self, registry):
        t = make_tool(dependencies=[
            ToolDependency(tool_id="dep_a"),
            ToolDependency(tool_id="dep_b", optional=True),
        ])
        registry.register(t)
        deps = registry.get_dependencies("test_tool")
        assert len(deps) == 2
        assert deps[0].tool_id == "dep_a"
        assert registry.get_dependencies("nonexistent") == []

    def test_get_dependents(self, registry):
        t_a = make_tool("a")
        t_b = make_tool("b", dependencies=[ToolDependency(tool_id="a")])
        t_c = make_tool("c", dependencies=[ToolDependency(tool_id="a")])
        registry.register(t_a)
        registry.register(t_b)
        registry.register(t_c)
        dependents = registry.get_dependents("a")
        assert len(dependents) == 2
        assert {d.id for d in dependents} == {"b", "c"}

    def test_get_dependents_none(self, registry):
        t = make_tool()
        registry.register(t)
        assert registry.get_dependents("test_tool") == []


class TestRegistryPermissions:
    def test_get_permission(self, registry):
        t = make_tool(permission=PermissionLevel.ADMIN)
        registry.register(t)
        assert registry.get_permission("test_tool") == PermissionLevel.ADMIN
        assert registry.get_permission("nonexistent") is None

    def test_get_tools_by_permission(self, registry):
        registry.register(make_tool("a", permission=PermissionLevel.USER))
        registry.register(make_tool("b", permission=PermissionLevel.ADMIN))
        registry.register(make_tool("c", permission=PermissionLevel.USER))
        user_tools = registry.get_tools_by_permission(PermissionLevel.USER)
        assert len(user_tools) == 2
        admin_tools = registry.get_tools_by_permission(PermissionLevel.ADMIN)
        assert len(admin_tools) == 1

    def test_check_permission(self, registry):
        t = make_tool("user_tool", permission=PermissionLevel.USER)
        registry.register(t)
        assert registry.check_permission("user_tool", PermissionLevel.USER) is True
        assert registry.check_permission("user_tool", PermissionLevel.ADMIN) is False
        assert registry.check_permission("nonexistent", PermissionLevel.USER) is False


class TestRegistryNoEventBus:
    def test_no_event_bus_does_not_crash(self):
        registry = ToolRegistry(event_bus=None)
        t = make_tool()
        registry.register(t)
        registry.remove("test_tool")
        registry.update_tool_health("test_tool", ToolHealth(status="healthy"))
        assert registry.count() == 0

    def test_event_bus_publish_error_does_not_crash(self, registry, event_bus):
        event_bus.publish.side_effect = RuntimeError("bus error")
        t = make_tool()
        registry.register(t)
        assert registry.count() == 1


class TestRegistryEnabled:
    def test_default_enabled(self, registry):
        t = make_tool("test_tool")
        registry.register(t)
        assert t.enabled is True
        assert registry.is_enabled("test_tool") is True

    def test_set_enabled_false(self, registry):
        t = make_tool("test_tool")
        registry.register(t)
        assert registry.set_enabled("test_tool", False) is True
        assert registry.is_enabled("test_tool") is False

    def test_set_enabled_true(self, registry):
        t = make_tool("test_tool", enabled=False)
        registry.register(t)
        registry.set_enabled("test_tool", True)
        assert registry.is_enabled("test_tool") is True

    def test_set_enabled_nonexistent(self, registry):
        assert registry.set_enabled("nonexistent", False) is False

    def test_get_enabled_tools(self, registry):
        t1 = make_tool("a", enabled=True)
        t2 = make_tool("b", enabled=False)
        t3 = make_tool("c", enabled=True)
        registry.register(t1)
        registry.register(t2)
        registry.register(t3)
        enabled = registry.get_enabled_tools()
        assert len(enabled) == 2
        assert {t.id for t in enabled} == {"a", "c"}

    def test_get_disabled_tools(self, registry):
        t1 = make_tool("a", enabled=True)
        t2 = make_tool("b", enabled=False)
        registry.register(t1)
        registry.register(t2)
        disabled = registry.get_disabled_tools()
        assert len(disabled) == 1
        assert disabled[0].id == "b"

    def test_is_enabled_nonexistent(self, registry):
        assert registry.is_enabled("nonexistent") is False


class TestRegistrySearch:
    def test_search_by_name(self, registry):
        t1 = make_tool("file_read", "File Reader")
        t2 = make_tool("net_get", "Network Get")
        registry.register(t1)
        registry.register(t2)
        results = registry.search("File")
        assert len(results) >= 1
        assert any(r.id == "file_read" for r in results)

    def test_search_by_id(self, registry):
        t = make_tool("filesystem.read")
        registry.register(t)
        results = registry.search("filesystem")
        assert len(results) >= 1

    def test_search_limit(self, registry):
        for i in range(10):
            registry.register(make_tool(f"tool_{i}", f"Tool {i}"))
        results = registry.search("Tool", limit=5)
        assert len(results) == 5

    def test_search_empty(self, registry):
        results = registry.search("nothing")
        assert results == []


class TestRegistryEdgeCases:
    def test_register_same_id_different_category(self, registry):
        t1 = make_tool("same_id", category=ToolCategory.FILESYSTEM)
        t2 = make_tool("same_id", category=ToolCategory.BROWSER)
        registry.register(t1)
        registry.register(t2)
        # Old category deindexed
        assert len(registry.get_by_category(ToolCategory.FILESYSTEM)) == 0
        assert len(registry.get_by_category(ToolCategory.BROWSER)) == 1

    def test_remove_updates_category_index(self, registry):
        t = make_tool("a", category=ToolCategory.FILESYSTEM)
        registry.register(t)
        registry.remove("a")
        assert len(registry.get_by_category(ToolCategory.FILESYSTEM)) == 0

    def test_remove_updates_tag_index(self, registry):
        t = make_tool("a", tags=["read", "write"])
        registry.register(t)
        registry.remove("a")
        assert len(registry.search_by_tags(["read"])) == 0
        assert len(registry.search_by_tags(["write"])) == 0
