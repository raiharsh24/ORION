import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from app.plugins.base import (
    Plugin, PluginState, PluginVersion, PluginMetadata,
    PluginDependency, PluginPermission, PluginHealth, PluginManifest,
)
from app.plugins.events import (
    PluginInstalled, PluginLoaded, PluginEnabled, PluginDisabled,
    PluginUnloaded, PluginRemoved, PluginFailed,
)
from app.plugins.manifest import parse_manifest, validate_manifest, manifest_from_dict
from app.plugins.health import PluginEngineHealth
from app.plugins.permissions import PermissionValidator
from app.plugins.registry import PluginRegistry
from app.plugins.loader import PluginLoader


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def registry(event_bus):
    return PluginRegistry(event_bus=event_bus)


@pytest.fixture
def permission_validator():
    pv = PermissionValidator()
    pv.grant("filesystem.read")
    pv.grant("filesystem.write")
    pv.grant("network")
    return pv


@pytest.fixture
def loader(registry, permission_validator, event_bus):
    return PluginLoader(registry, permission_validator, event_bus)


@pytest.fixture
def sample_manifest():
    return PluginManifest(
        id="hello_plugin",
        name="Hello Plugin",
        version="1.0.0",
        author="Test Author",
        description="A test plugin",
        permissions=[
            PluginPermission(permission_id="filesystem.read", description="Read files"),
        ],
        min_friday_version="1.0.0",
    )


@pytest.fixture
def sample_manifest_dict():
    return {
        "id": "hello_plugin",
        "name": "Hello Plugin",
        "version": "1.0.0",
        "author": "Test Author",
        "description": "A test plugin",
        "dependencies": [
            {"id": "base_utils", "version": ">=1.0.0", "optional": False},
        ],
        "permissions": [
            {"id": "filesystem.read", "description": "Read files"},
        ],
        "required_capabilities": ["file_analysis"],
        "min_friday_version": "1.0.0",
    }


# ── PluginVersion Tests ───────────────────────────────────────────────────

class TestPluginVersion:
    def test_parse(self):
        assert PluginVersion.parse("1.2.3") == (1, 2, 3)
        assert PluginVersion.parse("0.0.1") == (0, 0, 1)

    def test_satisfies_exact(self):
        assert PluginVersion.satisfies("1.0.0", "1.0.0")

    def test_satisfies_gt(self):
        assert PluginVersion.satisfies("2.0.0", ">1.0.0")
        assert not PluginVersion.satisfies("1.0.0", ">1.0.0")

    def test_satisfies_gte(self):
        assert PluginVersion.satisfies("1.0.0", ">=1.0.0")
        assert PluginVersion.satisfies("2.0.0", ">=1.0.0")

    def test_satisfies_lt(self):
        assert PluginVersion.satisfies("0.9.0", "<1.0.0")
        assert not PluginVersion.satisfies("1.0.0", "<1.0.0")

    def test_satisfies_wildcard(self):
        assert PluginVersion.satisfies("2.0.0", "*")
        assert PluginVersion.satisfies("0.0.1", "*")


# ── Base Model Tests ──────────────────────────────────────────────────────

class TestBaseModels:
    def test_plugin_defaults(self):
        p = Plugin(id="test", name="Test")
        assert p.state == PluginState.INSTALLED
        assert p.version == "1.0.0"
        assert p.is_enabled is False

    def test_plugin_is_loaded(self):
        p = Plugin(id="test", name="Test", state=PluginState.LOADED)
        assert p.is_loaded is True

    def test_plugin_state_values(self):
        assert PluginState.INSTALLED.value == "installed"
        assert PluginState.ENABLED.value == "enabled"
        assert PluginState.FAILED.value == "failed"

    def test_plugin_health_defaults(self):
        h = PluginHealth()
        assert h.status == "unknown"
        assert h.crash_count == 0

    def test_plugin_metadata(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        m = PluginMetadata(
            id="p1", name="Test", version="1.0.0",
            author="A", description="D", state=PluginState.ENABLED,
            dependency_count=2, permission_count=1,
            is_enabled=True, installed_at=now,
        )
        assert m.id == "p1"
        assert m.is_enabled is True

    def test_plugin_dependency_defaults(self):
        d = PluginDependency(plugin_id="dep1")
        assert d.optional is False
        assert d.version_constraint == "*"

    def test_plugin_permission(self):
        p = PluginPermission(permission_id="network", granted=True)
        assert p.granted is True


# ── Manifest Tests ────────────────────────────────────────────────────────

class TestManifest:
    def test_manifest_from_dict(self, sample_manifest_dict):
        m = manifest_from_dict(sample_manifest_dict)
        assert m is not None
        assert m.id == "hello_plugin"
        assert m.version == "1.0.0"
        assert len(m.dependencies) == 1
        assert len(m.permissions) == 1
        assert "file_analysis" in m.required_capabilities

    def test_manifest_from_dict_missing_id(self):
        m = manifest_from_dict({"name": "No ID"})
        assert m is not None
        assert m.id == ""

    def test_manifest_from_dict_invalid(self):
        m = manifest_from_dict([])
        assert m is None

    def test_validate_manifest_valid(self, sample_manifest):
        errors = validate_manifest(sample_manifest)
        assert len(errors) == 0

    def test_validate_manifest_missing_id(self):
        m = PluginManifest(id="", name="Test", version="1.0.0")
        errors = validate_manifest(m)
        assert "Plugin id is required" in errors

    def test_validate_manifest_missing_name(self):
        m = PluginManifest(id="test", name="", version="1.0.0")
        errors = validate_manifest(m)
        assert "Plugin name is required" in errors

    def test_validate_manifest_missing_version(self):
        m = PluginManifest(id="test", name="Test", version="")
        errors = validate_manifest(m)
        assert "Plugin version is required" in errors

    def test_validate_manifest_invalid_version(self):
        m = PluginManifest(id="test", name="Test", version="abc")
        errors = validate_manifest(m)
        assert any("version" in e for e in errors)

    def test_parse_manifest_valid_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False) as f:
            json.dump({"id": "test", "name": "Test", "version": "1.0.0"}, f)
            f.flush()
            m = parse_manifest(Path(f.name))
            assert m is not None
            assert m.id == "test"

    def test_parse_manifest_missing_file(self):
        m = parse_manifest(Path("/nonexistent/plugin.json"))
        assert m is None

    def test_parse_manifest_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False) as f:
            f.write("not json")
            f.flush()
            m = parse_manifest(Path(f.name))
            assert m is None


# ── PermissionValidator Tests ─────────────────────────────────────────────

class TestPermissionValidator:
    def test_grant_and_check(self):
        pv = PermissionValidator()
        pv.grant("test_perm")
        assert pv.is_granted("test_perm") is True

    def test_not_granted(self):
        pv = PermissionValidator()
        assert pv.is_granted("unknown") is False

    def test_revoke(self):
        pv = PermissionValidator()
        pv.grant("temp")
        pv.revoke("temp")
        assert pv.is_granted("temp") is False

    def test_validate_all_granted(self):
        pv = PermissionValidator()
        pv.grant("a")
        pv.grant("b")
        perms = [
            PluginPermission(permission_id="a"),
            PluginPermission(permission_id="b"),
        ]
        errors = pv.validate(perms)
        assert len(errors) == 0

    def test_validate_missing(self):
        pv = PermissionValidator()
        pv.grant("a")
        perms = [
            PluginPermission(permission_id="a"),
            PluginPermission(permission_id="missing"),
        ]
        errors = pv.validate(perms)
        assert len(errors) == 1

    def test_validate_pre_install_fails(self):
        pv = PermissionValidator()
        perms = [PluginPermission(permission_id="not_granted")]
        errors = pv.validate_pre_install(perms)
        assert len(errors) > 0


# ── Registry Tests ────────────────────────────────────────────────────────

class TestRegistry:
    def test_install(self, registry, sample_manifest):
        plugin = registry.install(sample_manifest)
        assert plugin is not None
        assert plugin.state == PluginState.INSTALLED
        assert registry.count() == 1

    def test_install_duplicate(self, registry, sample_manifest):
        registry.install(sample_manifest)
        plugin = registry.install(sample_manifest)
        assert plugin is None

    def test_install_publishes_event(self, registry, sample_manifest, event_bus):
        registry.install(sample_manifest)
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], PluginInstalled)
        ]
        assert len(events) == 1

    def test_get(self, registry, sample_manifest):
        registry.install(sample_manifest)
        p = registry.get("hello_plugin")
        assert p is not None
        assert p.name == "Hello Plugin"

    def test_get_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_remove(self, registry, sample_manifest):
        registry.install(sample_manifest)
        assert registry.remove("hello_plugin") is True
        assert registry.count() == 0

    def test_remove_publishes_event(self, registry, sample_manifest, event_bus):
        registry.install(sample_manifest)
        event_bus.reset_mock()
        registry.remove("hello_plugin")
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], PluginRemoved)
        ]
        assert len(events) == 1

    def test_remove_missing(self, registry):
        assert registry.remove("nonexistent") is False

    def test_update_state(self, registry, sample_manifest):
        registry.install(sample_manifest)
        registry.update_state("hello_plugin", PluginState.ENABLED)
        p = registry.get("hello_plugin")
        assert p.is_enabled is True

    def test_update_state_tracks_health(self, registry, sample_manifest):
        registry.install(sample_manifest)
        registry.update_state("hello_plugin", PluginState.FAILED, error="Boom")
        h = registry.get_health("hello_plugin")
        assert h.crash_count == 1
        assert h.last_error == "Boom"
        assert h.status == "failed"

    def test_list_plugins(self, registry, sample_manifest):
        registry.install(sample_manifest)
        assert len(registry.list_plugins()) == 1

    def test_list_metadata(self, registry, sample_manifest):
        registry.install(sample_manifest)
        metas = registry.list_metadata()
        assert len(metas) == 1
        assert metas[0].id == "hello_plugin"

    def test_list_by_state(self, registry, sample_manifest):
        registry.install(sample_manifest)
        registry.update_state("hello_plugin", PluginState.ENABLED)
        enabled = registry.list_by_state(PluginState.ENABLED)
        assert len(enabled) == 1

    def test_search(self, registry, sample_manifest):
        registry.install(sample_manifest)
        results = registry.search("Hello")
        assert len(results) == 1
        results2 = registry.search("nonexistent")
        assert len(results2) == 0

    def test_dependency_graph(self, registry, sample_manifest):
        registry.install(sample_manifest)
        graph = registry.get_dependency_graph()
        assert "hello_plugin" in graph
        assert graph["hello_plugin"] == []

    def test_get_dependents(self, registry, sample_manifest):
        registry.install(sample_manifest)
        deps = registry.get_dependents("hello_plugin")
        assert deps == []

    def test_health_defaults(self, registry):
        h = registry.aggregate_health()
        assert h.total_plugins == 0

    def test_health_after_install(self, registry, sample_manifest):
        registry.install(sample_manifest)
        h = registry.aggregate_health()
        assert h.total_plugins == 1

    def test_get_health(self, registry, sample_manifest):
        registry.install(sample_manifest)
        h = registry.get_health("hello_plugin")
        assert h is not None
        assert h.status == "installed"

    def test_update_health(self, registry, sample_manifest):
        registry.install(sample_manifest)
        registry.update_health("hello_plugin", load_time_ms=15.5)
        h = registry.get_health("hello_plugin")
        assert h.load_time_ms == 15.5

    def test_no_event_bus_does_not_crash(self):
        r = PluginRegistry(event_bus=None)
        m = PluginManifest(id="safe", name="Safe", version="1.0.0")
        assert r.install(m) is not None


# ── Loader Tests ──────────────────────────────────────────────────────────

class TestLoader:
    def test_load_plugin(self, loader, registry, sample_manifest):
        plugin = loader.load_plugin(sample_manifest)
        assert plugin is not None
        assert plugin.state == PluginState.LOADED

    def test_load_plugin_duplicate_id(self, loader, sample_manifest):
        loader.load_plugin(sample_manifest)
        plugin = loader.load_plugin(sample_manifest)
        assert plugin is None

    def test_load_plugin_invalid_manifest(self, loader):
        m = PluginManifest(id="", name="", version="")
        plugin = loader.load_plugin(m)
        assert plugin is None

    def test_load_plugin_permission_failure(self, loader):
        pv = PermissionValidator()
        r = PluginRegistry(event_bus=None)
        ldr = PluginLoader(r, pv, event_bus=None)
        m = PluginManifest(
            id="risky", name="Risky", version="1.0.0",
            permissions=[PluginPermission(permission_id="admin.access")],
        )
        plugin = ldr.load_plugin(m)
        assert plugin is None

    def test_load_plugin_publishes_event(self, loader, sample_manifest, event_bus):
        loader.load_plugin(sample_manifest)
        events = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], PluginLoaded)
        ]
        assert len(events) >= 1

    def test_enable_plugin(self, loader, registry, sample_manifest):
        loader.load_plugin(sample_manifest)
        assert loader.enable_plugin("hello_plugin") is True
        p = registry.get("hello_plugin")
        assert p.is_enabled is True

    def test_enable_missing_plugin(self, loader):
        assert loader.enable_plugin("nonexistent") is False

    def test_disable_plugin(self, loader, registry, sample_manifest):
        loader.load_plugin(sample_manifest)
        loader.enable_plugin("hello_plugin")
        assert loader.disable_plugin("hello_plugin") is True
        p = registry.get("hello_plugin")
        assert p.state == PluginState.DISABLED

    def test_unload_plugin(self, loader, registry, sample_manifest):
        loader.load_plugin(sample_manifest)
        assert loader.unload_plugin("hello_plugin") is True
        p = registry.get("hello_plugin")
        assert p.state == PluginState.UNLOADED

    def test_unload_missing_plugin(self, loader):
        assert loader.unload_plugin("nonexistent") is False

    def test_load_from_directory_empty(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = loader.load_from_directory(tmpdir)
            assert len(results["loaded"]) == 0
            assert len(results["failed"]) == 0

    def test_load_from_directory_with_plugin(self, loader, sample_manifest):
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "hello_plugin"
            plugin_dir.mkdir()
            manifest_path = plugin_dir / "plugin.json"
            manifest_path.write_text(json.dumps({
                "id": "hello_plugin",
                "name": "Hello Plugin",
                "version": "1.0.0",
                "author": "Test",
                "description": "Test",
                "permissions": [{"id": "filesystem.read", "description": "Read"}],
            }))
            results = loader.load_from_directory(tmpdir)
            assert "hello_plugin" in results["loaded"]

    def test_load_from_directory_invalid_manifest(self, loader):
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "bad_plugin"
            plugin_dir.mkdir()
            manifest_path = plugin_dir / "plugin.json"
            manifest_path.write_text("not json")
            results = loader.load_from_directory(tmpdir)
            assert len(results["failed"]) > 0 or len(results["loaded"]) == 0


# ── Dependency Resolution Tests ───────────────────────────────────────────

class TestDependencyResolution:
    def test_resolve_dependencies(self, loader, registry):
        base = PluginManifest(
            id="base_utils", name="Base Utils", version="1.0.0",
        )
        loader.load_plugin(base)
        loader.enable_plugin("base_utils")

        dep_manifest = PluginManifest(
            id="advanced", name="Advanced", version="1.0.0",
            dependencies=[PluginDependency(plugin_id="base_utils")],
        )
        plugin = loader.load_plugin(dep_manifest)
        assert plugin is not None
        assert plugin.state == PluginState.LOADED

    def test_unresolved_dependency_fails(self, loader):
        dep_manifest = PluginManifest(
            id="orphan", name="Orphan", version="1.0.0",
            dependencies=[PluginDependency(plugin_id="missing_dep")],
        )
        plugin = loader.load_plugin(dep_manifest)
        assert plugin is None

    def test_optional_dependency_allowed(self, loader):
        dep_manifest = PluginManifest(
            id="flexible", name="Flexible", version="1.0.0",
            dependencies=[
                PluginDependency(plugin_id="missing_opt", optional=True),
            ],
        )
        plugin = loader.load_plugin(dep_manifest)
        assert plugin is not None

    def test_dependency_not_enabled_fails(self, loader, registry):
        base = PluginManifest(
            id="base_utils", name="Base Utils", version="1.0.0",
        )
        loader.load_plugin(base)

        dep_manifest = PluginManifest(
            id="advanced", name="Advanced", version="1.0.0",
            dependencies=[PluginDependency(plugin_id="base_utils")],
        )
        plugin = loader.load_plugin(dep_manifest)
        assert plugin is None


# ── Event Tests ───────────────────────────────────────────────────────────

class TestEvents:
    def test_plugin_installed_event(self):
        e = PluginInstalled(plugin_id="p1", name="Test", version="1.0.0")
        assert e.topic == "PluginInstalled"
        assert e.data["plugin_id"] == "p1"

    def test_plugin_loaded_event(self):
        e = PluginLoaded(plugin_id="p1", name="Test", load_time_ms=10.0)
        assert e.topic == "PluginLoaded"
        assert e.data["load_time_ms"] == 10.0

    def test_plugin_enabled_event(self):
        e = PluginEnabled(plugin_id="p1", name="Test")
        assert e.topic == "PluginEnabled"

    def test_plugin_disabled_event(self):
        e = PluginDisabled(plugin_id="p1", name="Test")
        assert e.topic == "PluginDisabled"

    def test_plugin_unloaded_event(self):
        e = PluginUnloaded(plugin_id="p1", name="Test")
        assert e.topic == "PluginUnloaded"

    def test_plugin_removed_event(self):
        e = PluginRemoved(plugin_id="p1", name="Test")
        assert e.topic == "PluginRemoved"

    def test_plugin_failed_event(self):
        e = PluginFailed(plugin_id="p1", name="Test", error="Something broke")
        assert e.topic == "PluginFailed"
        assert "Something broke" in e.data["error"]


# ── Health Tests ──────────────────────────────────────────────────────────

class TestHealth:
    def test_engine_health_defaults(self):
        h = PluginEngineHealth()
        assert h.total_plugins == 0
        assert h.total_crashes == 0

    def test_engine_health_after_install(self, registry, sample_manifest):
        registry.install(sample_manifest)
        h = registry.aggregate_health()
        assert h.total_plugins == 1


# ── Lifecycle Tests ───────────────────────────────────────────────────────

class TestLifecycle:
    def test_full_lifecycle(self, registry, loader):
        m = PluginManifest(
            id="lifecycle", name="Lifecycle", version="2.0.0",
        )
        p = loader.load_plugin(m)
        assert p.state == PluginState.LOADED
        assert registry.count() == 1

        loader.enable_plugin("lifecycle")
        assert registry.get("lifecycle").state == PluginState.ENABLED

        loader.disable_plugin("lifecycle")
        assert registry.get("lifecycle").state == PluginState.DISABLED

        loader.unload_plugin("lifecycle")
        assert registry.get("lifecycle").state == PluginState.UNLOADED

        registry.remove("lifecycle")
        assert registry.count() == 0
