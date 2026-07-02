import pytest
import time
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock

from app.capabilities.base import (
    CapabilityDefinition, CapabilityMetadata, CapabilityCategory,
    CapabilityStatus, CapabilityDependency, CapabilityHealth,
    CapabilityPermission, CapabilityResult, CapabilityResolution,
)
from app.capabilities.events import (
    CapabilityRegistered, CapabilityRemoved, CapabilityResolved,
    CapabilityHealthChanged, CapabilityExecuted,
)
from app.capabilities.metadata import build_metadata
from app.capabilities.health import CapabilityEngineHealth
from app.capabilities.registry import CapabilityRegistry
from app.capabilities.resolver import CapabilityResolver
from app.capabilities.defaults import (
    DEFAULT_CAPABILITIES, web_search, terminal, workflow_control,
)
from app.tool_selection.base import ToolSelectionContext, ToolSelectionResult
from app.tool_selection.selector import ToolSelectionEngine


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def registry(event_bus):
    return CapabilityRegistry(event_bus=event_bus)


@pytest.fixture
def tool_selection():
    return MagicMock(spec=ToolSelectionEngine)


@pytest.fixture
def resolver(registry, tool_selection, event_bus):
    return CapabilityResolver(registry, tool_selection, event_bus)


@pytest.fixture
def sample_cap():
    return CapabilityDefinition(
        id="test_cap",
        name="Test Capability",
        description="A test capability",
        category=CapabilityCategory.CUSTOM,
        version="1.0.0",
        aliases=["test", "t"],
        tool_ids=["tool_a", "tool_b"],
        tags=["test"],
        permission_level="user",
    )


@pytest.fixture
def dependent_cap():
    return CapabilityDefinition(
        id="dependent",
        name="Dependent Capability",
        description="Depends on test_cap",
        category=CapabilityCategory.CUSTOM,
        version="1.0.0",
        dependencies=[
            CapabilityDependency(capability_id="test_cap", optional=False),
        ],
        tool_ids=["tool_c"],
    )


# ── Base Model Tests ──────────────────────────────────────────────────────

class TestBaseModels:
    def test_capability_definition_defaults(self):
        c = CapabilityDefinition(id="c1", name="Test", description="desc")
        assert c.status == CapabilityStatus.ACTIVE
        assert c.category == CapabilityCategory.CUSTOM
        assert c.version == "1.0.0"
        assert c.aliases == []

    def test_capability_status_values(self):
        assert CapabilityStatus.ACTIVE.value == "active"
        assert CapabilityStatus.DEPRECATED.value == "deprecated"

    def test_capability_category_values(self):
        assert CapabilityCategory.WEB_SEARCH.value == "web_search"
        assert CapabilityCategory.FILE_ANALYSIS.value == "file_analysis"

    def test_capability_health_defaults(self):
        h = CapabilityHealth()
        assert h.availability is True
        assert h.status == "unknown"
        assert h.execution_success_count == 0

    def test_capability_result_defaults(self):
        r = CapabilityResult(capability_id="c1")
        assert r.success is False
        assert r.duration_ms == 0.0

    def test_capability_resolution_defaults(self):
        r = CapabilityResolution(capability_id="c1", capability_name="Test")
        assert r.confidence == 1.0
        assert r.errors == []

    def test_capability_permission_defaults(self):
        p = CapabilityPermission(capability_id="c1")
        assert p.required_level == "user"

    def test_build_metadata(self, sample_cap):
        m = build_metadata(sample_cap)
        assert m.id == "test_cap"
        assert m.name == "Test Capability"
        assert m.tool_count == 2
        assert m.dependency_count == 0


# ── Registry Tests ───────────────────────────────────────────────────────

class TestRegistry:
    def test_register(self, registry, sample_cap):
        registry.register(sample_cap)
        assert registry.has_capability("test_cap")
        assert registry.count() == 1

    def test_register_publishes_event(self, registry, sample_cap, event_bus):
        registry.register(sample_cap)
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], CapabilityRegistered)
        ]
        assert len(events) == 1

    def test_get(self, registry, sample_cap):
        registry.register(sample_cap)
        c = registry.get("test_cap")
        assert c is not None
        assert c.name == "Test Capability"

    def test_get_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_get_by_alias(self, registry, sample_cap):
        registry.register(sample_cap)
        c = registry.get_by_alias("test")
        assert c is not None
        assert c.id == "test_cap"

    def test_resolve_alias(self, registry, sample_cap):
        registry.register(sample_cap)
        c = registry.resolve_alias("test")
        assert c is not None
        assert c.id == "test_cap"
        c2 = registry.resolve_alias("test_cap")
        assert c2 is not None

    def test_unregister(self, registry, sample_cap):
        registry.register(sample_cap)
        assert registry.unregister("test_cap") is True
        assert registry.count() == 0

    def test_unregister_publishes_event(self, registry, sample_cap, event_bus):
        registry.register(sample_cap)
        event_bus.reset_mock()
        registry.unregister("test_cap")
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], CapabilityRemoved)
        ]
        assert len(events) == 1

    def test_unregister_missing(self, registry):
        assert registry.unregister("nonexistent") is False

    def test_list_capabilities(self, registry, sample_cap):
        registry.register(sample_cap)
        caps = registry.list_capabilities()
        assert len(caps) == 1

    def test_list_metadata(self, registry, sample_cap):
        registry.register(sample_cap)
        metas = registry.list_metadata()
        assert len(metas) == 1
        assert isinstance(metas[0], CapabilityMetadata)

    def test_list_by_category(self, registry, sample_cap):
        registry.register(sample_cap)
        caps = registry.list_by_category(CapabilityCategory.CUSTOM)
        assert len(caps) == 1
        caps2 = registry.list_by_category(CapabilityCategory.WEB_SEARCH)
        assert len(caps2) == 0

    def test_list_by_status(self, registry, sample_cap):
        registry.register(sample_cap)
        caps = registry.list_by_status(CapabilityStatus.ACTIVE)
        assert len(caps) == 1
        caps2 = registry.list_by_status(CapabilityStatus.DEPRECATED)
        assert len(caps2) == 0

    def test_search(self, registry, sample_cap):
        registry.register(sample_cap)
        assert len(registry.search("test")) >= 1
        assert len(registry.search("nonexistent")) == 0

    def test_get_health(self, registry, sample_cap):
        registry.register(sample_cap)
        h = registry.get_health("test_cap")
        assert h is not None
        assert h.availability is True

    def test_update_health_success(self, registry, sample_cap):
        registry.register(sample_cap)
        registry.update_health("test_cap", success=True, duration_ms=10.0)
        h = registry.get_health("test_cap")
        assert h.execution_success_count == 1
        assert h.execution_failure_count == 0

    def test_update_health_failure(self, registry, sample_cap, event_bus):
        registry.register(sample_cap)
        for _ in range(5):
            registry.update_health("test_cap", success=False, duration_ms=5.0)
        h = registry.get_health("test_cap")
        assert h.execution_failure_count == 5
        assert h.status == "unhealthy"

    def test_set_availability(self, registry, sample_cap, event_bus):
        registry.register(sample_cap)
        registry.set_availability("test_cap", False, "Service down")
        h = registry.get_health("test_cap")
        assert h.availability is False
        assert h.status == "unavailable"

    def test_health_change_event(self, registry, sample_cap, event_bus):
        registry.register(sample_cap)
        event_bus.reset_mock()
        registry.set_availability("test_cap", False, "Down")
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], CapabilityHealthChanged)
        ]
        assert len(events) >= 1

    def test_get_permission(self, registry, sample_cap):
        registry.register(sample_cap)
        p = registry.get_permission("test_cap")
        assert p is not None
        assert p.required_level == "user"

    def test_get_permission_custom(self, registry, sample_cap):
        perm = CapabilityPermission(
            capability_id="test_cap", required_level="admin",
        )
        registry.register(sample_cap, permission=perm)
        p = registry.get_permission("test_cap")
        assert p.required_level == "admin"

    def test_get_dependencies(self, registry, dependent_cap, sample_cap):
        registry.register(sample_cap)
        registry.register(dependent_cap)
        deps = registry.get_dependencies("dependent")
        assert len(deps) == 1
        assert deps[0].capability_id == "test_cap"

    def test_get_dependency_graph(self, registry, dependent_cap, sample_cap):
        registry.register(sample_cap)
        registry.register(dependent_cap)
        graph = registry.get_dependency_graph()
        assert "dependent" in graph
        assert graph["dependent"] == ["test_cap"]
        assert graph["test_cap"] == []

    def test_aggregate_health_empty(self, registry):
        h = registry.aggregate_health()
        assert h.total_capabilities == 0
        assert h.success_rate == 100.0

    def test_aggregate_health_with_caps(self, registry, sample_cap):
        registry.register(sample_cap)
        h = registry.aggregate_health()
        assert h.total_capabilities == 1
        assert h.active_capabilities == 1

    def test_record_resolution(self, registry):
        registry.record_resolution()
        assert registry.aggregate_health().resolved_count == 1

    def test_record_execution(self, registry):
        registry.record_execution(True)
        registry.record_execution(False)
        h = registry.aggregate_health()
        assert h.execution_count == 1
        assert h.failure_count == 1
        assert h.success_rate == 50.0

    def test_version_tracking(self, registry):
        c1 = CapabilityDefinition(
            id="v1", name="V1", description="",
            category=CapabilityCategory.CUSTOM, version="1.0.0",
        )
        c2 = CapabilityDefinition(
            id="v2", name="V2", description="",
            category=CapabilityCategory.CUSTOM, version="2.0.0",
        )
        registry.register(c1)
        registry.register(c2)
        assert registry.get("v1").version == "1.0.0"
        assert registry.get("v2").version == "2.0.0"


# ── Resolver Tests ───────────────────────────────────────────────────────

class TestResolver:
    def test_resolve_not_found(self, resolver):
        r = resolver.resolve("nonexistent")
        assert len(r.errors) > 0
        assert "not found" in r.errors[0]

    def test_resolve_by_alias(self, resolver, registry, sample_cap):
        registry.register(sample_cap)
        r = resolver.resolve("test")
        assert len(r.errors) == 0
        assert r.capability_id == "test_cap"

    def test_resolve_inactive(self, resolver, registry):
        c = CapabilityDefinition(
            id="inactive", name="Inactive", description="",
            category=CapabilityCategory.CUSTOM,
            status=CapabilityStatus.DISABLED,
        )
        registry.register(c)
        r = resolver.resolve("inactive")
        assert len(r.errors) > 0
        assert "not active" in r.errors[0]

    def test_resolve_with_dependencies(self, resolver, registry, sample_cap, dependent_cap):
        registry.register(sample_cap)
        registry.register(dependent_cap)
        r = resolver.resolve("dependent")
        assert len(r.errors) == 0
        assert "test_cap" in r.resolved_dependencies

    def test_resolve_unresolved_dependency(self, resolver, registry, dependent_cap):
        registry.register(dependent_cap)
        r = resolver.resolve("dependent")
        assert len(r.errors) > 0
        assert "Unresolved" in r.errors[0]

    def test_resolve_optional_dependency(self, resolver, registry, sample_cap):
        c = CapabilityDefinition(
            id="opt_dep", name="Opt", description="",
            category=CapabilityCategory.CUSTOM,
            dependencies=[
                CapabilityDependency(capability_id="missing", optional=True),
            ],
            tool_ids=["tool_a"],
        )
        registry.register(sample_cap)
        registry.register(c)
        r = resolver.resolve("opt_dep")
        assert len(r.errors) == 0

    def test_resolve_returns_tool_ids(self, resolver, registry, sample_cap):
        registry.register(sample_cap)
        r = resolver.resolve("test_cap")
        assert "tool_a" in r.resolved_tool_ids
        assert "tool_b" in r.resolved_tool_ids

    def test_resolve_multi(self, resolver, registry, sample_cap, dependent_cap):
        registry.register(sample_cap)
        registry.register(dependent_cap)
        results = resolver.resolve_multi(["test_cap", "dependent"])
        assert len(results) == 2
        assert results["test_cap"].errors == []
        assert results["dependent"].errors == []

    def test_resolve_multi_with_deps(self, resolver, registry, sample_cap, dependent_cap):
        registry.register(sample_cap)
        registry.register(dependent_cap)
        results = resolver.resolve_multi(["dependent"])
        assert len(results) == 2
        assert "test_cap" in results

    @pytest.mark.anyio
    async def test_resolve_with_selection(self, resolver, registry, sample_cap, tool_selection):
        registry.register(sample_cap)
        tool_selection.select = AsyncMock(return_value=ToolSelectionResult(
            selected_tools=[],
            confidence=1.0,
        ))
        result = await resolver.resolve_with_selection("test_cap")
        assert result.confidence == 1.0
        tool_selection.select.assert_called_once()

    @pytest.mark.anyio
    async def test_resolve_with_selection_errors(self, resolver, registry):
        result = await resolver.resolve_with_selection("nonexistent")
        assert result.confidence == 0.0
        assert len(result.errors) > 0

    def test_resolve_publishes_event(self, resolver, registry, sample_cap, event_bus):
        registry.register(sample_cap)
        resolver.resolve("test_cap")
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], CapabilityResolved)
        ]
        assert len(events) >= 1


# ── Defaults Tests ────────────────────────────────────────────────────────

class TestDefaults:
    def test_default_web_search(self):
        c = web_search()
        assert c.id == "web_search"
        assert c.category == CapabilityCategory.WEB_SEARCH
        assert "search" in c.aliases

    def test_default_terminal(self):
        c = terminal()
        assert c.id == "terminal"
        assert c.permission_level == "elevated"

    def test_default_workflow_control(self):
        c = workflow_control()
        assert c.id == "workflow_control"
        assert c.category == CapabilityCategory.WORKFLOW_CONTROL

    def test_all_defaults(self):
        caps = DEFAULT_CAPABILITIES()
        assert len(caps) == 11
        ids = [c.id for c in caps]
        assert "web_search" in ids
        assert "file_analysis" in ids
        assert "desktop_automation" in ids
        assert "knowledge_retrieval" in ids
        assert "memory_access" in ids
        assert "vision" in ids
        assert "voice" in ids
        assert "terminal" in ids
        assert "workflow_control" in ids
        assert "browser" in ids
        assert "code_execution" in ids

    def test_defaults_register(self, registry):
        for c in DEFAULT_CAPABILITIES():
            registry.register(c)
        assert registry.count() == 11


# ── Event Tests ───────────────────────────────────────────────────────────

class TestEvents:
    def test_capability_registered_event(self):
        e = CapabilityRegistered(
            capability_id="c1", name="Test",
            category="custom", version="1.0.0",
        )
        assert e.topic == "CapabilityRegistered"
        assert e.data["capability_id"] == "c1"

    def test_capability_removed_event(self):
        e = CapabilityRemoved(capability_id="c1", name="Test")
        assert e.topic == "CapabilityRemoved"

    def test_capability_resolved_event(self):
        e = CapabilityResolved(
            capability_id="c1", name="Test",
            resolved_tools=3, duration_ms=5.0,
        )
        assert e.topic == "CapabilityResolved"
        assert e.data["resolved_tools"] == 3

    def test_capability_health_changed_event(self):
        e = CapabilityHealthChanged(
            capability_id="c1", name="Test",
            old_status="healthy", new_status="degraded",
        )
        assert e.topic == "CapabilityHealthChanged"

    def test_capability_executed_event(self):
        e = CapabilityExecuted(
            capability_id="c1", name="Test",
            success=True, duration_ms=10.0, tool_count=2,
        )
        assert e.topic == "CapabilityExecuted"
        assert e.data["success"] is True


# ── Health Tests ──────────────────────────────────────────────────────────

class TestHealth:
    def test_engine_health_defaults(self):
        h = CapabilityEngineHealth()
        assert h.total_capabilities == 0
        assert h.success_rate == 100.0

    def test_engine_health_from_registry(self, registry, sample_cap):
        registry.register(sample_cap)
        h = registry.aggregate_health()
        assert h.total_capabilities == 1
        assert h.active_capabilities == 1

    def test_engine_health_tracks_unhealthy(self, registry, sample_cap):
        registry.register(sample_cap)
        for _ in range(6):
            registry.update_health("test_cap", success=False)
        h = registry.aggregate_health()
        assert h.details["unhealthy"] >= 1


# ── Permission Tests ──────────────────────────────────────────────────────

class TestPermissions:
    def test_default_permission(self, registry, sample_cap):
        registry.register(sample_cap)
        p = registry.get_permission("test_cap")
        assert p.required_level == "user"

    def test_custom_permission(self, registry, sample_cap):
        perm = CapabilityPermission(
            capability_id="test_cap",
            required_level="admin",
            allowed_roles=["admin", "superuser"],
        )
        registry.register(sample_cap, permission=perm)
        p = registry.get_permission("test_cap")
        assert p.required_level == "admin"
        assert "admin" in p.allowed_roles


# ── Alias Tests ───────────────────────────────────────────────────────────

class TestAliases:
    def test_resolve_by_alias(self, registry):
        c = CapabilityDefinition(
            id="long_name", name="Long", description="",
            category=CapabilityCategory.CUSTOM,
            aliases=["short", "s"],
        )
        registry.register(c)
        assert registry.get_by_alias("short") is not None
        assert registry.get_by_alias("s") is not None
        assert registry.get_by_alias("missing") is None

    def test_alias_removed_on_unregister(self, registry):
        c = CapabilityDefinition(
            id="with_alias", name="With", description="",
            category=CapabilityCategory.CUSTOM,
            aliases=["w"],
        )
        registry.register(c)
        registry.unregister("with_alias")
        assert registry.get_by_alias("w") is None

    def test_search_by_alias(self, registry):
        c = CapabilityDefinition(
            id="searchable", name="Searchable", description="desc",
            category=CapabilityCategory.CUSTOM,
            aliases=["find_me"],
        )
        registry.register(c)
        results = registry.search("find_me")
        assert len(results) == 1


# ── Versioning Tests ──────────────────────────────────────────────────────

class TestVersioning:
    def test_version_default(self):
        c = CapabilityDefinition(id="v", name="V", description="")
        assert c.version == "1.0.0"

    def test_version_stored(self, registry):
        c = CapabilityDefinition(
            id="ver", name="Ver", description="",
            category=CapabilityCategory.CUSTOM, version="2.1.0",
        )
        registry.register(c)
        assert registry.get("ver").version == "2.1.0"

    def test_metadata_version(self, registry):
        c = CapabilityDefinition(
            id="meta", name="Meta", description="",
            category=CapabilityCategory.CUSTOM, version="3.0.0",
        )
        registry.register(c)
        m = registry.get_metadata("meta")
        assert m.version == "3.0.0"


# ── Resolution Integration Tests ──────────────────────────────────────────

class TestResolutionIntegration:
    def test_resolve_chain(self, registry, resolver):
        a = CapabilityDefinition(
            id="cap_a", name="A", description="",
            category=CapabilityCategory.CUSTOM,
            tool_ids=["tool_1"],
        )
        b = CapabilityDefinition(
            id="cap_b", name="B", description="",
            category=CapabilityCategory.CUSTOM,
            dependencies=[CapabilityDependency(capability_id="cap_a")],
            tool_ids=["tool_2"],
        )
        c = CapabilityDefinition(
            id="cap_c", name="C", description="",
            category=CapabilityCategory.CUSTOM,
            dependencies=[CapabilityDependency(capability_id="cap_b")],
            tool_ids=["tool_3"],
        )
        registry.register(a)
        registry.register(b)
        registry.register(c)

        r = resolver.resolve("cap_c")
        assert len(r.errors) == 0
        assert "cap_a" in r.resolved_dependencies
        assert "cap_b" in r.resolved_dependencies
        assert "tool_3" in r.resolved_tool_ids

    def test_resolve_partial_failure(self, registry, resolver):
        a = CapabilityDefinition(
            id="good", name="Good", description="",
            category=CapabilityCategory.CUSTOM,
            tool_ids=["tool_a"],
        )
        b = CapabilityDefinition(
            id="bad_dep", name="Bad", description="",
            category=CapabilityCategory.CUSTOM,
            dependencies=[CapabilityDependency(capability_id="missing")],
            tool_ids=["tool_b"],
        )
        registry.register(a)
        registry.register(b)

        r_a = resolver.resolve("good")
        assert len(r_a.errors) == 0

        r_b = resolver.resolve("bad_dep")
        assert len(r_b.errors) > 0

    def test_no_event_bus_does_not_crash(self):
        r = CapabilityRegistry(event_bus=None)
        c = CapabilityDefinition(id="safe", name="Safe", description="",
                                 category=CapabilityCategory.CUSTOM)
        r.register(c)
        assert r.has_capability("safe")
        assert r.count() == 1


# ── Lifecycle Tests ───────────────────────────────────────────────────────

class TestLifecycle:
    def test_full_lifecycle(self, registry, event_bus):
        c = CapabilityDefinition(
            id="lifecycle", name="Lifecycle", description="Full cycle",
            category=CapabilityCategory.CUSTOM,
            aliases=["lc"],
            tool_ids=["tool_x"],
            tags=["test"],
        )
        registry.register(c)
        assert registry.count() == 1
        assert registry.has_capability("lifecycle")

        h = registry.get_health("lifecycle")
        assert h.status == "active"

        registry.update_health("lifecycle", success=True, duration_ms=5.0)
        h = registry.get_health("lifecycle")
        assert h.execution_success_count == 1

        registry.set_availability("lifecycle", False, "Under maintenance")
        h = registry.get_health("lifecycle")
        assert h.availability is False

        perm = registry.get_permission("lifecycle")
        assert perm is not None

        deps = registry.get_dependencies("lifecycle")
        assert deps == []

        meta = registry.get_metadata("lifecycle")
        assert meta is not None
        assert meta.tool_count == 1

        assert registry.unregister("lifecycle") is True
        assert registry.count() == 0
