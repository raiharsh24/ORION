import os
import json
import time
import tempfile
import shutil
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.plugins.registry import PluginRegistry as SdkPluginRegistry
from app.plugins.base import PluginManifest, PluginDependency, PluginPermission
from app.plugin_runtime.base import (
    PluginRuntimeState, PluginRuntimeConfig, PluginInstance,
    SandboxConfig, ResourceQuota, ExecutionStats,
)
from app.plugin_runtime.runtime import PluginRuntime
from app.plugin_runtime.sandbox import Sandbox
from app.plugin_runtime.loader import RuntimePluginLoader
from app.plugin_runtime.unloader import PluginUnloader
from app.plugin_runtime.reloader import PluginReloader
from app.plugin_runtime.monitor import PluginMonitor
from app.plugin_runtime.registry import PluginRuntimeRegistry
from app.plugin_runtime.permissions import PermissionEnforcer
from app.plugin_runtime.security import SecurityConfig, SecurityPolicy
from app.plugin_runtime.health import PluginRuntimeHealth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return MagicMock()

@pytest.fixture
def sdk_registry(event_bus):
    return SdkPluginRegistry(event_bus=event_bus)

@pytest.fixture
def temp_plugin_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

def make_manifest(plugin_id="test_plugin", name="Test Plugin",
                  version="1.0.0", deps=None, perms=None):
    return {
        "id": plugin_id,
        "name": name,
        "version": version,
        "author": "Test",
        "description": "A test plugin",
        "dependencies": deps or [],
        "permissions": perms or [],
        "entry_point": "",
    }

def create_test_plugin(base_dir, plugin_id="test_plugin",
                       name="Test Plugin", version="1.0.0",
                       deps=None, perms=None):
    plugin_dir = Path(base_dir) / plugin_id
    plugin_dir.mkdir(exist_ok=True)
    manifest = make_manifest(plugin_id, name, version, deps, perms)
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
    return str(plugin_dir)

@pytest.fixture
def runtime(event_bus):
    sdk = SdkPluginRegistry(event_bus=event_bus)
    config = PluginRuntimeConfig(
        plugin_dirs=[],
        watch_enabled=False,
        auto_load=False,
        sandbox_enabled=True,
    )
    rt = PluginRuntime(sdk_registry=sdk, event_bus=event_bus, config=config)
    return rt

@pytest.fixture
def sandbox(event_bus):
    return Sandbox(event_bus=event_bus)


# ---------------------------------------------------------------------------
# Base Model Tests
# ---------------------------------------------------------------------------

class TestPluginRuntimeState:
    def test_enum_values(self):
        assert PluginRuntimeState.DISCOVERED.value == "discovered"
        assert PluginRuntimeState.READY.value == "ready"
        assert PluginRuntimeState.FAILED.value == "failed"
        assert PluginRuntimeState.SUSPENDED.value == "suspended"

class TestPluginInstance:
    def test_default_state(self):
        inst = PluginInstance(plugin_id="p1", name="Test")
        assert inst.state == PluginRuntimeState.DISCOVERED
        assert inst.error_count == 0
        assert inst.reload_count == 0

    def test_record_state(self):
        inst = PluginInstance(plugin_id="p1", name="Test")
        inst.record_state(PluginRuntimeState.LOADED)
        assert inst.state == PluginRuntimeState.LOADED
        assert len(inst.state_history) == 1

    def test_is_running(self):
        ready = PluginInstance(plugin_id="p1", name="Test",
                                state=PluginRuntimeState.READY)
        assert ready.is_running is True
        failed = PluginInstance(plugin_id="p1", name="Test",
                                 state=PluginRuntimeState.FAILED)
        assert failed.is_running is False

    def test_is_loadable(self):
        d = PluginInstance(plugin_id="p1", name="Test",
                            state=PluginRuntimeState.DISCOVERED)
        assert d.is_loadable is True
        r = PluginInstance(plugin_id="p1", name="Test",
                            state=PluginRuntimeState.READY)
        assert r.is_loadable is False

class TestResourceQuota:
    def test_defaults(self):
        q = ResourceQuota()
        assert q.max_memory_mb == 256.0
        assert q.max_execution_time_ms == 30000.0

class TestExecutionStats:
    def test_defaults(self):
        s = ExecutionStats()
        assert s.total_executions == 0
        assert s.average_execution_time_ms == 0.0

class TestPluginRuntimeHealth:
    def test_defaults(self):
        h = PluginRuntimeHealth()
        assert h.overall_status == "unknown"
        assert h.total_plugins == 0

    def test_to_dict(self):
        h = PluginRuntimeHealth(overall_status="healthy", total_plugins=3)
        d = h.to_dict()
        assert d["overall_status"] == "healthy"
        assert d["total_plugins"] == 3


# ---------------------------------------------------------------------------
# Sandbox Tests
# ---------------------------------------------------------------------------

class TestSandbox:
    @pytest.mark.anyio
    async def test_execute_success(self, sandbox):
        async def ok():
            return 42
        result = await sandbox.execute("p1", "Test", ok())
        assert result == 42

    @pytest.mark.anyio
    async def test_execute_timeout(self, sandbox):
        async def slow():
            await asyncio.sleep(10)
            return 1
        with pytest.raises(TimeoutError):
            await sandbox.execute("p1", "Test", slow(), timeout_ms=10)

    @pytest.mark.anyio
    async def test_execute_sync(self, sandbox):
        result = await sandbox.execute_sync("p1", "Test", lambda: 99)
        assert result == 99

    def test_validate_imports_allowed(self, sandbox):
        assert sandbox.validate_imports({"json": "1.0"}) is True

    def test_validate_imports_blocked(self, sandbox):
        sandbox._config.restrict_imports = True
        assert sandbox.validate_imports({"os": "1.0"}) is False
        assert sandbox.validate_imports({"subprocess": "1.0"}) is False

    @pytest.mark.anyio
    async def test_check_filesystem_access(self, sandbox, event_bus):
        perms = sandbox.permission_enforcer
        perms.grant("p1", "filesystem.read")
        ok = await sandbox.check_filesystem_access("p1", "Test", "/tmp/test")
        assert ok is True

    @pytest.mark.anyio
    async def test_check_filesystem_access_denied(self, sandbox):
        ok = await sandbox.check_filesystem_access("p1", "Test", "/tmp/test")
        assert ok is False

    @pytest.mark.anyio
    async def test_sandbox_violation_count(self, sandbox):
        assert sandbox.violation_count == 0
        await sandbox.check_import("p1", "Test", "os")
        assert sandbox.violation_count > 0


# ---------------------------------------------------------------------------
# PermissionEnforcer Tests
# ---------------------------------------------------------------------------

class TestPermissionEnforcer:
    def test_grant_and_check(self):
        pe = PermissionEnforcer()
        assert pe.is_granted("p1", "filesystem.read") is False
        pe.grant("p1", "filesystem.read")
        assert pe.is_granted("p1", "filesystem.read") is True

    def test_revoke(self):
        pe = PermissionEnforcer()
        pe.grant("p1", "test")
        pe.revoke("p1", "test")
        assert pe.is_granted("p1", "test") is False

    def test_wildcard(self):
        pe = PermissionEnforcer()
        pe.grant("p1", "*")
        assert pe.is_granted("p1", "anything") is True

    def test_check_permission(self):
        pe = PermissionEnforcer()
        pe.grant("p1", "filesystem.read")
        assert pe.check_permission("p1", "Test", "filesystem.read", "/tmp") is True
        assert pe.check_permission("p1", "Test", "missing.perm", "/tmp") is False

    def test_violations(self):
        pe = PermissionEnforcer()
        pe.check_permission("p1", "Test", "missing.perm", "detail")
        assert len(pe.get_violations("p1")) == 1
        assert len(pe.get_violations()) == 1

    def test_grant_from_manifest(self):
        pe = PermissionEnforcer()
        pe.grant_from_manifest("p1", [
            PluginPermission(permission_id="filesystem.read"),
            PluginPermission(permission_id="network"),
        ])
        assert pe.is_granted("p1", "filesystem.read") is True
        assert pe.is_granted("p1", "network") is True

    def test_clear(self):
        pe = PermissionEnforcer()
        pe.check_permission("p1", "Test", "x", "")
        pe.reset()
        assert pe.violation_count == 0

    def test_filesystem_access_no_perm(self, sandbox):
        pe = PermissionEnforcer()
        assert pe.check_filesystem_access("p1", "Test", "/tmp") is False

    def test_filesystem_access_with_perm(self):
        pe = PermissionEnforcer()
        pe.grant("p1", "filesystem.read")
        assert pe.check_filesystem_access("p1", "Test", "/tmp") is True

    def test_network_access(self):
        pe = PermissionEnforcer()
        pe.grant("p1", "network")
        assert pe.check_network_access("p1", "Test", "example.com", 80) is True

    def test_network_access_denied(self):
        pe = PermissionEnforcer()
        assert pe.check_network_access("p1", "Test", "example.com", 80) is False


# ---------------------------------------------------------------------------
# Monitor Tests
# ---------------------------------------------------------------------------

class TestPluginMonitor:
    def test_record_execution(self):
        m = PluginMonitor()
        m.record_execution("p1", 100.0, success=True)
        stats = m.get_execution_stats("p1")
        assert stats.total_executions == 1
        assert stats.successful_executions == 1

    def test_record_crash(self):
        m = PluginMonitor()
        m.record_crash("p1", "Test", "error", "execute")
        history = m.get_crash_history("p1")
        assert len(history) == 1
        assert history[0].error == "error"

    def test_average_load_time(self):
        m = PluginMonitor()
        assert m.get_average_load_time() == 0.0
        m.record_load("p1", 50.0)
        m.record_load("p2", 150.0)
        assert m.get_average_load_time() == 100.0

    def test_peak_plugins(self):
        m = PluginMonitor()
        m.set_peak_plugins(5)
        m.set_peak_plugins(3)
        assert m._peak_plugins == 5

    def test_get_health_empty(self):
        m = PluginMonitor()
        h = m.get_health({})
        assert h.total_plugins == 0
        assert h.overall_status == "healthy"

    def test_get_health_with_instances(self):
        m = PluginMonitor()
        inst = PluginInstance(plugin_id="p1", name="Test",
                               state=PluginRuntimeState.READY)
        h = m.get_health({"p1": inst})
        assert h.total_plugins == 1
        assert h.running_plugins == 1

    def test_get_health_crash_history(self):
        m = PluginMonitor()
        m.record_crash("p1", "Test", "err", "run")
        h = m.get_health({})
        assert h.last_crash is not None

    def test_reset(self):
        m = PluginMonitor()
        m.record_execution("p1", 10.0, True)
        m.reset()
        assert m.get_execution_stats("p1").total_executions == 0


# ---------------------------------------------------------------------------
# Security Tests
# ---------------------------------------------------------------------------

class TestSecurityPolicy:
    def test_is_import_allowed(self):
        sp = SecurityPolicy()
        assert sp.is_import_allowed("json") is True
        assert sp.is_import_allowed("os") is False
        assert sp.is_import_allowed("subprocess") is False

    def test_get_import_permission(self):
        sp = SecurityPolicy()
        assert sp.get_import_permission("os") == "filesystem.read"
        assert sp.get_import_permission("json") is None


# ---------------------------------------------------------------------------
# Runtime Loader Tests
# ---------------------------------------------------------------------------

class TestRuntimePluginLoader:
    @pytest.mark.anyio
    async def test_discover_plugins(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        discovered = runtime.loader.discover(temp_plugin_dir)
        assert "plugin_a" in discovered
        inst = runtime.loader.get_instance("plugin_a")
        assert inst is not None
        assert inst.state == PluginRuntimeState.DISCOVERED

    @pytest.mark.anyio
    async def test_discover_empty_dir(self, runtime, temp_plugin_dir):
        discovered = runtime.loader.discover(temp_plugin_dir)
        assert discovered == []

    @pytest.mark.anyio
    async def test_discover_nonexistent_dir(self, runtime):
        discovered = runtime.loader.discover("/nonexistent/path")
        assert discovered == []

    @pytest.mark.anyio
    async def test_load_plugin(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        inst = await runtime.loader.load("plugin_a")
        assert inst is not None
        assert inst.state == PluginRuntimeState.LOADED

    @pytest.mark.anyio
    async def test_load_nonexistent(self, runtime):
        inst = await runtime.loader.load("missing")
        assert inst is None

    @pytest.mark.anyio
    async def test_initialize_plugin(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.loader.load("plugin_a")
        ok = await runtime.loader.initialize("plugin_a")
        assert ok is True
        inst = runtime.loader.get_instance("plugin_a")
        assert inst.state == PluginRuntimeState.INITIALIZED

    @pytest.mark.anyio
    async def test_mark_ready(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.loader.load("plugin_a")
        await runtime.loader.initialize("plugin_a")
        ok = await runtime.loader.mark_ready("plugin_a")
        assert ok is True
        inst = runtime.loader.get_instance("plugin_a")
        assert inst.state == PluginRuntimeState.READY

    @pytest.mark.anyio
    async def test_full_lifecycle(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        inst = await runtime.loader.load("plugin_a")
        assert inst is not None
        await runtime.loader.initialize("plugin_a")
        await runtime.loader.mark_ready("plugin_a")
        inst = runtime.loader.get_instance("plugin_a")
        assert inst.state == PluginRuntimeState.READY


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------

class TestPluginRuntimeRegistry:
    def test_list_plugins(self, runtime):
        reg = runtime.registry
        assert reg.list_plugins() == []
        assert reg.count() == 0

    def test_search(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "my_plugin", name="My Cool Plugin")
        runtime.loader.discover(temp_plugin_dir)
        results = runtime.registry.search("cool")
        assert len(results) == 1
        assert results[0].plugin_id == "my_plugin"

    def test_list_by_state(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        d = runtime.registry.list_by_state(PluginRuntimeState.DISCOVERED)
        assert len(d) == 1

    def test_get_dependency_graph(self, runtime):
        graph = runtime.registry.get_dependency_graph()
        assert isinstance(graph, dict)

    def test_check_dependency_chain(self, runtime):
        assert runtime.registry.check_dependency_chain("missing") is True


# ---------------------------------------------------------------------------
# PluginRuntime Integration Tests
# ---------------------------------------------------------------------------

class TestPluginRuntime:
    @pytest.mark.anyio
    async def test_start_and_shutdown(self, runtime):
        await runtime.start()
        await runtime.shutdown()

    @pytest.mark.anyio
    async def test_load_and_unload(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        inst = await runtime.load_plugin("plugin_a")
        assert inst is not None
        assert inst.state == PluginRuntimeState.READY

        ok = await runtime.unload_plugin("plugin_a")
        assert ok is True
        assert runtime.loader.get_instance("plugin_a") is None

    @pytest.mark.anyio
    async def test_suspend_and_resume(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")

        ok = await runtime.suspend_plugin("plugin_a", "testing")
        assert ok is True
        inst = runtime.loader.get_instance("plugin_a")
        assert inst.state == PluginRuntimeState.SUSPENDED

        ok = await runtime.resume_plugin("plugin_a")
        assert ok is True
        assert inst.state == PluginRuntimeState.READY

    @pytest.mark.anyio
    async def test_suspend_not_ready(self, runtime):
        ok = await runtime.suspend_plugin("missing")
        assert ok is False

    @pytest.mark.anyio
    async def test_execute(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")

        async def my_func():
            return 42
        result = await runtime.execute("plugin_a", my_func())
        assert result == 42

    @pytest.mark.anyio
    async def test_execute_not_found(self, runtime):
        async def my_func():
            return 1
        with pytest.raises(ValueError):
            await runtime.execute("missing", my_func())

    @pytest.mark.anyio
    async def test_execute_timeout(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")

        async def slow():
            await asyncio.sleep(10)
            return 1
        with pytest.raises(TimeoutError):
            await runtime.execute("plugin_a", slow(), timeout_ms=10)

    @pytest.mark.anyio
    async def test_reload_plugin(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")
        inst = runtime.loader.get_instance("plugin_a")
        assert inst.reload_count == 0

        await runtime.reloader.start_watching(temp_plugin_dir)
        reloaded = await runtime.reload_plugin("plugin_a")
        assert reloaded is not None
        assert reloaded.reload_count == 1
        await runtime.reloader.stop_watching()

    @pytest.mark.anyio
    async def test_health(self, runtime):
        h = runtime.health()
        assert isinstance(h, PluginRuntimeHealth)

    @pytest.mark.anyio
    async def test_multiple_plugins(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        create_test_plugin(temp_plugin_dir, "plugin_b",
                           name="Plugin B")
        create_test_plugin(temp_plugin_dir, "plugin_c",
                           name="Plugin C")

        discovered = runtime.loader.discover(temp_plugin_dir)
        assert len(discovered) == 3

        for pid in discovered:
            await runtime.load_plugin(pid)

        assert runtime.registry.count() == 3
        h = runtime.health()
        assert h.total_plugins == 3

    @pytest.mark.anyio
    async def test_concurrent_loading(self, runtime, temp_plugin_dir):
        for i in range(5):
            create_test_plugin(temp_plugin_dir, f"p{i}",
                               name=f"Plugin {i}")
        runtime.loader.discover(temp_plugin_dir)
        tasks = [runtime.load_plugin(f"p{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)
        assert all(r is not None for r in results)


# ---------------------------------------------------------------------------
# Unloader Tests
# ---------------------------------------------------------------------------

class TestPluginUnloader:
    @pytest.mark.anyio
    async def test_unload(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")
        ok = await runtime.unload_plugin("plugin_a")
        assert ok is True

    @pytest.mark.anyio
    async def test_unload_missing(self, runtime):
        ok = await runtime.unload_plugin("missing")
        assert ok is False


# ---------------------------------------------------------------------------
# Reloader Tests
# ---------------------------------------------------------------------------

class TestPluginReloader:
    @pytest.mark.anyio
    async def test_watch_start_stop(self, runtime, temp_plugin_dir):
        await runtime.reloader.start_watching(temp_plugin_dir)
        await runtime.reloader.stop_watching()

    @pytest.mark.anyio
    async def test_reload_on_change(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")

        reloaded = await runtime.reload_plugin("plugin_a")
        assert reloaded is not None
        assert reloaded.reload_count == 1

    @pytest.mark.anyio
    async def test_reload_callbacks(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")

        called = []
        async def on_reload(pid):
            called.append(pid)
        runtime.reloader.on_reload(on_reload)

        await runtime.reload_plugin("plugin_a")
        assert "plugin_a" in called


# ---------------------------------------------------------------------------
# DI Integration Tests
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_plugin_runtime(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("plugin_runtime")
            assert svc is not None
            assert hasattr(svc, "health")
            assert hasattr(svc, "load_plugin")
            assert hasattr(svc, "sandbox")

            h = kernel.health()
            assert hasattr(h, "plugin_runtime")
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_plugin_runtime_registered_in_module_registry(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            modules = kernel.module_registry.list_modules()
            module_names = modules if isinstance(modules, list) else list(modules)
            assert "plugin_runtime" in module_names
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_plugin_runtime_health_in_kernel_health(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            health = kernel.health()
            assert health.plugin_runtime.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()


# ---------------------------------------------------------------------------
# Resource Cleanup Tests
# ---------------------------------------------------------------------------

class TestResourceCleanup:
    @pytest.mark.anyio
    async def test_cleanup_after_unload(self, runtime, temp_plugin_dir):
        create_test_plugin(temp_plugin_dir, "plugin_a")
        runtime.loader.discover(temp_plugin_dir)
        await runtime.load_plugin("plugin_a")
        await runtime.unload_plugin("plugin_a")
        assert runtime.loader.get_instance("plugin_a") is None
        assert runtime.permission_enforcer.violation_count >= 0

    @pytest.mark.anyio
    async def test_cleanup_after_failure(self, runtime, temp_plugin_dir):
        bad_plugin_dir = Path(temp_plugin_dir) / "bad_plugin"
        bad_plugin_dir.mkdir(exist_ok=True)
        (bad_plugin_dir / "plugin.json").write_text("not valid json")

        discovered = runtime.loader.discover(temp_plugin_dir)
        assert "bad_plugin" not in discovered

    @pytest.mark.anyio
    async def test_multiple_start_stop(self, runtime):
        for _ in range(3):
            await runtime.start()
            await runtime.shutdown()
