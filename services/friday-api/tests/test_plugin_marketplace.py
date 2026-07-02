import os
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.plugin_marketplace.base import (
    PluginPackage, PackageStatus, PackageDependency,
    MarketplaceConfig, CacheEntry, SearchResult,
    InstallResult, UpdateResult, UninstallResult,
    DependencyResolution, DependencyGraph, DependencyNode,
    PackageIntegrityInfo,
)
from app.plugin_marketplace.manifest import (
    parse_package_manifest, manifest_to_dict, validate_manifest,
)
from app.plugin_marketplace.package import PackageBuilder, PackageIntegrity
from app.plugin_marketplace.cache import PackageCache
from app.plugin_marketplace.search import PluginSearch
from app.plugin_marketplace.resolver import DependencyResolver
from app.plugin_marketplace.registry import MarketplaceRegistry
from app.plugin_marketplace.repository import RepositoryManager
from app.plugin_marketplace.health import MarketplaceHealth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return MagicMock()

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

@pytest.fixture
def config(temp_dir):
    return MarketplaceConfig(
        local_repository_path=os.path.join(temp_dir, "plugins"),
        cache_path=os.path.join(temp_dir, "cache"),
    )

@pytest.fixture
def sample_pkg():
    return PluginPackage(
        id="test_plugin",
        name="Test Plugin",
        version="1.0.0",
        author="Test Author",
        description="A test plugin",
        dependencies=[PackageDependency(plugin_id="base_utils")],
    )

@pytest.fixture
def sample_pkg_dict():
    return {
        "id": "test_plugin",
        "name": "Test Plugin",
        "version": "1.0.0",
        "author": "Test Author",
        "description": "A test plugin",
        "dependencies": [{"plugin_id": "base_utils", "version": ">=1.0.0"}],
        "categories": ["utility"],
        "tags": ["test"],
    }


# ---------------------------------------------------------------------------
# Base Model Tests
# ---------------------------------------------------------------------------

class TestPackageStatus:
    def test_enum_values(self):
        assert PackageStatus.INSTALLED.value == "installed"
        assert PackageStatus.BROKEN.value == "broken"
        assert PackageStatus.CONFLICTED.value == "conflicted"

class TestPluginPackage:
    def test_defaults(self, sample_pkg):
        assert sample_pkg.is_installed is False
        assert sample_pkg.is_broken is False

    def test_is_installed(self, sample_pkg):
        sample_pkg.status = PackageStatus.INSTALLED
        assert sample_pkg.is_installed is True

    def test_is_broken(self, sample_pkg):
        sample_pkg.status = PackageStatus.BROKEN
        assert sample_pkg.is_broken is True


# ---------------------------------------------------------------------------
# Manifest Tests
# ---------------------------------------------------------------------------

class TestManifest:
    def test_parse_valid(self, temp_dir, sample_pkg_dict):
        path = Path(temp_dir) / "plugin.json"
        path.write_text(json.dumps(sample_pkg_dict))
        pkg = parse_package_manifest(path)
        assert pkg is not None
        assert pkg.id == "test_plugin"
        assert pkg.version == "1.0.0"

    def test_parse_invalid_json(self, temp_dir):
        path = Path(temp_dir) / "plugin.json"
        path.write_text("not json")
        pkg = parse_package_manifest(path)
        assert pkg is None

    def test_parse_nonexistent(self, temp_dir):
        path = Path(temp_dir) / "nonexistent.json"
        pkg = parse_package_manifest(path)
        assert pkg is None

    def test_validate_manifest_valid(self, sample_pkg):
        errors = validate_manifest(sample_pkg)
        assert errors == []

    def test_validate_manifest_missing_id(self):
        pkg = PluginPackage(id="", name="Test", version="1.0.0")
        errors = validate_manifest(pkg)
        assert "Missing required field: id" in errors

    def test_validate_manifest_invalid_version(self):
        pkg = PluginPackage(id="test", name="Test", version="abc")
        errors = validate_manifest(pkg)
        assert any("Invalid version" in e for e in errors)

    def test_manifest_to_dict(self, sample_pkg):
        d = manifest_to_dict(sample_pkg)
        assert d["id"] == "test_plugin"
        assert d["name"] == "Test Plugin"
        assert "dependencies" in d


# ---------------------------------------------------------------------------
# PackageBuilder Tests
# ---------------------------------------------------------------------------

class TestPackageBuilder:
    def test_from_directory(self, temp_dir, sample_pkg_dict):
        pkg_dir = Path(temp_dir) / "test_plugin"
        pkg_dir.mkdir()
        (pkg_dir / "plugin.json").write_text(json.dumps(sample_pkg_dict))
        pkg = PackageBuilder.from_directory(str(pkg_dir))
        assert pkg is not None
        assert pkg.id == "test_plugin"

    def test_from_dict(self, sample_pkg_dict):
        pkg = PackageBuilder.from_dict(sample_pkg_dict)
        assert pkg is not None
        assert pkg.id == "test_plugin"

    def test_to_dict(self, sample_pkg):
        d = PackageBuilder.to_dict(sample_pkg)
        assert d["id"] == "test_plugin"


# ---------------------------------------------------------------------------
# PackageIntegrity Tests
# ---------------------------------------------------------------------------

class TestPackageIntegrity:
    def test_verify_no_hash(self, temp_dir):
        pkg = PluginPackage(id="test", name="Test", version="1.0.0")
        path = os.path.join(temp_dir, "test.txt")
        Path(path).write_text("hello")
        info = PackageIntegrity.verify(pkg, path)
        assert info.verified is True

    def test_verify_mismatch(self, temp_dir):
        pkg = PluginPackage(id="test", name="Test", version="1.0.0",
                             integrity_hash="abc123")
        path = os.path.join(temp_dir, "test.txt")
        Path(path).write_text("hello")
        info = PackageIntegrity.verify(pkg, path)
        assert info.verified is False

    def test_verify_file_not_found(self, temp_dir):
        pkg = PluginPackage(id="test", name="Test", version="1.0.0",
                             integrity_hash="abc123")
        path = os.path.join(temp_dir, "missing.txt")
        info = PackageIntegrity.verify(pkg, path)
        assert info.errors


# ---------------------------------------------------------------------------
# Cache Tests
# ---------------------------------------------------------------------------

class TestPackageCache:
    def test_get_miss(self, config):
        cache = PackageCache(config)
        result = cache.get("missing", "1.0.0")
        assert result is None

    def test_put_and_get(self, config):
        cache = PackageCache(config)
        data = {"test": "data"}
        path = cache.put("test_pkg", "1.0.0", data)
        assert path is not None

        result = cache.get("test_pkg", "1.0.0")
        assert result is not None

    def test_remove(self, config):
        cache = PackageCache(config)
        cache.put("test_pkg", "1.0.0", {"a": 1})
        assert cache.remove("test_pkg", "1.0.0") is True
        assert cache.get("test_pkg", "1.0.0") is None

    def test_clear(self, config):
        cache = PackageCache(config)
        cache.put("p1", "1.0.0", {"a": 1})
        cache.put("p2", "1.0.0", {"b": 2})
        assert cache.clear() == 2
        assert cache.get_statistics()["entries"] == 0

    def test_statistics(self, config):
        cache = PackageCache(config)
        stats = cache.get_statistics()
        assert "hit_rate" in stats
        assert "size_mb" in stats


# ---------------------------------------------------------------------------
# Repository Tests
# ---------------------------------------------------------------------------

class TestRepositoryManager:
    def test_scan_empty(self, config):
        repo = RepositoryManager(config)
        result = repo.scan_local_repository()
        assert result["total"] == 0

    def test_add_and_get(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        pkg = repo.get_package("test_plugin")
        assert pkg is not None
        assert pkg.name == "Test Plugin"

    def test_remove(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        assert repo.remove_package("test_plugin") is True
        assert repo.get_package("test_plugin") is None

    def test_get_all(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        all_pkgs = repo.get_all_packages()
        assert len(all_pkgs) == 1

    def test_get_installed(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        installed = repo.get_installed({"test_plugin"})
        assert len(installed) == 1

    def test_get_available_updates(self, config):
        repo = RepositoryManager(config)
        old = PluginPackage(id="p1", name="P1", version="1.0.0")
        new = PluginPackage(id="p1", name="P1", version="2.0.0")
        repo.add_package(new)
        updates = repo.get_available_updates({"p1": "1.0.0"})
        assert len(updates) == 1
        assert updates[0].version == "2.0.0"

    def test_get_statistics(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        stats = repo.get_statistics()
        assert stats["total_packages"] == 1


# ---------------------------------------------------------------------------
# Search Tests
# ---------------------------------------------------------------------------

class TestPluginSearch:
    def test_search_by_name(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        search = PluginSearch(repo)
        result = search.search("Test")
        assert result.total == 1

    def test_search_no_results(self, config, sample_pkg):
        repo = RepositoryManager(config)
        repo.add_package(sample_pkg)
        search = PluginSearch(repo)
        result = search.search("nonexistent")
        assert result.total == 0

    def test_search_by_category(self, config, sample_pkg):
        repo = RepositoryManager(config)
        sample_pkg.categories = ["utility"]
        repo.add_package(sample_pkg)
        search = PluginSearch(repo)
        result = search.search("Test", category="utility")
        assert result.total == 1

    def test_get_featured(self, config):
        repo = RepositoryManager(config)
        pkg = PluginPackage(id="f1", name="F1", version="1.0.0",
                             featured=True)
        repo.add_package(pkg)
        search = PluginSearch(repo)
        featured = search.get_featured()
        assert len(featured) == 1


# ---------------------------------------------------------------------------
# Dependency Resolution Tests
# ---------------------------------------------------------------------------

class TestDependencyResolver:
    def test_resolve_simple(self):
        resolver = DependencyResolver()
        packages = {
            "base": PluginPackage(id="base", name="Base", version="1.0.0"),
            "plugin": PluginPackage(
                id="plugin", name="Plugin", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="base")],
            ),
        }
        result = resolver.resolve("plugin", packages)
        assert result.success is True
        assert "base" in result.order

    def test_resolve_no_deps(self):
        resolver = DependencyResolver()
        packages = {
            "plugin": PluginPackage(id="plugin", name="Plugin", version="1.0.0"),
        }
        result = resolver.resolve("plugin", packages)
        assert result.success is True

    def test_resolve_missing_dep(self):
        resolver = DependencyResolver()
        packages = {
            "plugin": PluginPackage(
                id="plugin", name="Plugin", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="missing")],
            ),
        }
        result = resolver.resolve("plugin", packages)
        assert result.success is False
        assert "missing" in result.missing_dependencies

    def test_detect_circular(self):
        resolver = DependencyResolver()
        packages = {
            "a": PluginPackage(
                id="a", name="A", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="b")],
            ),
            "b": PluginPackage(
                id="b", name="B", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="a")],
            ),
        }
        result = resolver.resolve("a", packages)
        assert result.success is False
        assert len(result.circular_dependencies) > 0

    def test_transitive_deps(self):
        resolver = DependencyResolver()
        packages = {
            "a": PluginPackage(
                id="a", name="A", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="b")],
            ),
            "b": PluginPackage(
                id="b", name="B", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="c")],
            ),
            "c": PluginPackage(id="c", name="C", version="1.0.0"),
        }
        result = resolver.resolve("a", packages)
        assert result.success is True
        assert result.order.index("c") < result.order.index("b")
        assert result.order.index("b") < result.order.index("a")

    def test_dependency_order(self):
        resolver = DependencyResolver()
        packages = {
            "a": PluginPackage(
                id="a", name="A", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="b")],
            ),
            "b": PluginPackage(id="b", name="B", version="1.0.0"),
        }
        order = resolver.get_dependency_order(packages)
        assert "a" in order
        assert "b" in order

    def test_check_circular_no_cycle(self):
        resolver = DependencyResolver()
        packages = {
            "a": PluginPackage(id="a", name="A", version="1.0.0"),
            "b": PluginPackage(id="b", name="B", version="1.0.0"),
        }
        cycles = resolver.check_circular(packages)
        assert cycles == []

    def test_check_circular_with_cycle(self):
        resolver = DependencyResolver()
        packages = {
            "a": PluginPackage(
                id="a", name="A", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="b")],
            ),
            "b": PluginPackage(
                id="b", name="B", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="a")],
            ),
        }
        cycles = resolver.check_circular(packages)
        assert len(cycles) > 0


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------

class TestMarketplaceRegistry:
    def test_register_and_get(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        assert reg.get("test_plugin") is not None

    def test_unregister(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        assert reg.unregister("test_plugin") is True
        assert reg.get("test_plugin") is None

    def test_mark_installed(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        reg.mark_installed("test_plugin", "1.0.0")
        assert reg.is_installed("test_plugin") is True

    def test_mark_removed(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        reg.mark_installed("test_plugin", "1.0.0")
        reg.mark_removed("test_plugin")
        assert reg.is_installed("test_plugin") is False

    def test_mark_broken(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        reg.mark_broken("test_plugin")
        assert reg.get("test_plugin").status == PackageStatus.BROKEN

    def test_get_installed(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        reg.mark_installed("test_plugin", "1.0.0")
        installed = reg.get_installed()
        assert len(installed) == 1

    def test_get_installed_ids(self, sample_pkg):
        reg = MarketplaceRegistry()
        reg.register(sample_pkg)
        reg.mark_installed("test_plugin", "1.0.0")
        assert "test_plugin" in reg.get_installed_ids()


# ---------------------------------------------------------------------------
# Health Tests
# ---------------------------------------------------------------------------

class TestMarketplaceHealth:
    def test_defaults(self):
        h = MarketplaceHealth()
        assert h.overall_status == "unknown"
        assert h.installed_count == 0

    def test_to_dict(self):
        h = MarketplaceHealth(overall_status="healthy", installed_count=3)
        d = h.to_dict()
        assert d["overall_status"] == "healthy"
        assert d["installed_count"] == 3


# ---------------------------------------------------------------------------
# Installer / Updater / Uninstaller Integration Tests
# ---------------------------------------------------------------------------

class TestPackageManager:
    @pytest.mark.anyio
    async def test_start_and_shutdown(self, config):
        from app.plugin_marketplace.manager import PackageManager
        from app.plugin_runtime.runtime import PluginRuntime
        from app.plugins.registry import PluginRegistry as SdkPluginRegistry
        sdk = SdkPluginRegistry(event_bus=None)
        runtime = PluginRuntime(sdk_registry=sdk, config=None)
        pm = PackageManager(runtime=runtime, config=config)
        await pm.start()
        assert pm.registry is not None
        await pm.shutdown()

    @pytest.mark.anyio
    async def test_scan_repository(self, config, temp_dir):
        from app.plugin_marketplace.manager import PackageManager
        from app.plugin_runtime.runtime import PluginRuntime
        from app.plugins.registry import PluginRegistry as SdkPluginRegistry
        sdk = SdkPluginRegistry(event_bus=None)
        runtime = PluginRuntime(sdk_registry=sdk, config=None)
        pm = PackageManager(runtime=runtime, config=config)
        await pm.start()
        result = pm.scan_repository()
        assert "total" in result
        await pm.shutdown()

    @pytest.mark.anyio
    async def test_resolve_dependencies(self, config):
        from app.plugin_marketplace.manager import PackageManager
        from app.plugin_runtime.runtime import PluginRuntime
        from app.plugins.registry import PluginRegistry as SdkPluginRegistry
        sdk = SdkPluginRegistry(event_bus=None)
        runtime = PluginRuntime(sdk_registry=sdk, config=None)
        pm = PackageManager(runtime=runtime, config=config)
        await pm.start()

        pm.repository.add_package(
            PluginPackage(id="base", name="Base", version="1.0.0")
        )
        pm.repository.add_package(
            PluginPackage(
                id="plugin_a", name="Plugin A", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="base")],
            )
        )
        result = pm.resolve_dependencies("plugin_a")
        assert result.success is True
        assert "base" in result.order
        await pm.shutdown()

    @pytest.mark.anyio
    async def test_check_circular(self, config):
        from app.plugin_marketplace.manager import PackageManager
        from app.plugin_runtime.runtime import PluginRuntime
        from app.plugins.registry import PluginRegistry as SdkPluginRegistry
        sdk = SdkPluginRegistry(event_bus=None)
        runtime = PluginRuntime(sdk_registry=sdk, config=None)
        pm = PackageManager(runtime=runtime, config=config)
        await pm.start()

        pm.repository.add_package(
            PluginPackage(
                id="a", name="A", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="b")],
            )
        )
        pm.repository.add_package(
            PluginPackage(
                id="b", name="B", version="1.0.0",
                dependencies=[PackageDependency(plugin_id="a")],
            )
        )
        cycles = pm.check_circular_dependencies()
        assert len(cycles) > 0
        await pm.shutdown()

    def test_health(self, config):
        from app.plugin_marketplace.manager import PackageManager
        from app.plugin_runtime.runtime import PluginRuntime
        from app.plugins.registry import PluginRegistry as SdkPluginRegistry
        sdk = SdkPluginRegistry(event_bus=None)
        runtime = PluginRuntime(sdk_registry=sdk, config=None)
        pm = PackageManager(runtime=runtime, config=config)
        h = pm.health()
        assert isinstance(h, MarketplaceHealth)

    @pytest.mark.anyio
    async def test_search(self, config):
        from app.plugin_marketplace.manager import PackageManager
        from app.plugin_runtime.runtime import PluginRuntime
        from app.plugins.registry import PluginRegistry as SdkPluginRegistry
        sdk = SdkPluginRegistry(event_bus=None)
        runtime = PluginRuntime(sdk_registry=sdk, config=None)
        pm = PackageManager(runtime=runtime, config=config)
        await pm.start()

        pm.repository.add_package(
            PluginPackage(id="test", name="Test Plugin", version="1.0.0",
                           categories=["utility"])
        )
        result = pm.search_packages("Test")
        assert result.total == 1
        await pm.shutdown()


# ---------------------------------------------------------------------------
# Kernel Integration Tests
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_package_manager(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("package_manager")
            assert svc is not None
            assert hasattr(svc, "install")
            assert hasattr(svc, "health")

            h = kernel.health()
            assert hasattr(h, "plugin_marketplace")
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_package_manager_registered_in_module_registry(self):
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
            assert "package_manager" in module_names
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_package_manager_health_in_kernel_health(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            health = kernel.health()
            assert health.plugin_marketplace.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()
