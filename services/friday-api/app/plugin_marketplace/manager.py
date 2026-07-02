from typing import Optional, Any, Dict, List
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, MarketplaceConfig, InstallResult,
    UpdateResult, UninstallResult, SearchResult, DependencyResolution,
)
from app.plugin_marketplace.repository import RepositoryManager
from app.plugin_marketplace.cache import PackageCache
from app.plugin_marketplace.search import PluginSearch
from app.plugin_marketplace.resolver import DependencyResolver
from app.plugin_marketplace.installer import PackageInstaller
from app.plugin_marketplace.updater import PackageUpdater
from app.plugin_marketplace.uninstaller import PackageUninstaller
from app.plugin_marketplace.registry import MarketplaceRegistry
from app.plugin_marketplace.health import MarketplaceHealth
from app.plugin_runtime.runtime import PluginRuntime


class PackageManager:
    def __init__(
        self,
        runtime: PluginRuntime,
        event_bus: Optional[Any] = None,
        config: Optional[MarketplaceConfig] = None,
    ) -> None:
        self._config = config or MarketplaceConfig()
        self._event_bus = event_bus

        self._resolver = DependencyResolver(event_bus=event_bus)
        self._cache = PackageCache(self._config)
        self._repository = RepositoryManager(self._config, event_bus=event_bus)
        self._registry = MarketplaceRegistry()
        self._search = PluginSearch(self._repository)
        self._installer = PackageInstaller(
            runtime=runtime,
            resolver=self._resolver,
            cache=self._cache,
            config=self._config,
            event_bus=event_bus,
        )
        self._updater = PackageUpdater(
            runtime=runtime,
            resolver=self._resolver,
            cache=self._cache,
            config=self._config,
            event_bus=event_bus,
        )
        self._uninstaller = PackageUninstaller(
            runtime=runtime,
            resolver=self._resolver,
            cache=self._cache,
            config=self._config,
            event_bus=event_bus,
        )

    @property
    def repository(self) -> RepositoryManager:
        return self._repository

    @property
    def cache(self) -> PackageCache:
        return self._cache

    @property
    def search(self) -> PluginSearch:
        return self._search

    @property
    def resolver(self) -> DependencyResolver:
        return self._resolver

    @property
    def installer(self) -> PackageInstaller:
        return self._installer

    @property
    def updater(self) -> PackageUpdater:
        return self._updater

    @property
    def uninstaller(self) -> PackageUninstaller:
        return self._uninstaller

    @property
    def registry(self) -> MarketplaceRegistry:
        return self._registry

    async def start(self) -> None:
        logger.info("Package Manager starting...")
        scan_result = self._repository.scan_local_repository()
        for pkg in self._repository.get_all_packages():
            self._registry.register(pkg)
        logger.info(f"Package Manager started: {scan_result['total']} packages")

    async def shutdown(self) -> None:
        logger.info("Package Manager shut down")

    async def install(self, plugin_id: str,
                       force: bool = False) -> InstallResult:
        pkg = self._repository.get_package(plugin_id)
        if pkg is None:
            return InstallResult(
                plugin_id=plugin_id,
                errors=[f"Package '{plugin_id}' not found"],
            )
        result = await self._installer.install(
            pkg, self._repository.packages, force,
        )
        if result.success:
            self._registry.mark_installed(plugin_id, pkg.version)
        return result

    async def install_from_path(self, path: str) -> InstallResult:
        result = await self._installer.install_from_path(
            path, self._repository.packages,
        )
        if result.success:
            pkg = self._repository.get_package(result.plugin_id)
            if pkg:
                self._registry.mark_installed(result.plugin_id, pkg.version)
        return result

    async def update(self, plugin_id: str) -> UpdateResult:
        pkg = self._repository.get_package(plugin_id)
        if pkg is None:
            return UpdateResult(
                plugin_id=plugin_id,
                errors=[f"Package '{plugin_id}' not found"],
            )
        installed_version = self._registry._installed.get(plugin_id)
        if installed_version and installed_version == pkg.version:
            return UpdateResult(
                plugin_id=plugin_id,
                new_version=pkg.version,
                errors=["Already at latest version"],
            )
        result = await self._updater.update(pkg, pkg, self._repository.packages)
        if result.success:
            self._registry.mark_installed(plugin_id, pkg.version)
        return result

    async def rollback(self, plugin_id: str) -> UpdateResult:
        pkg = self._repository.get_package(plugin_id)
        if pkg is None:
            return UpdateResult(
                plugin_id=plugin_id,
                errors=[f"Package '{plugin_id}' not found"],
            )
        result = await self._updater.rollback(pkg)
        if result.success:
            self._registry.mark_installed(plugin_id, pkg.version)
        return result

    async def uninstall(self, plugin_id: str,
                         remove_dependents: bool = False) -> UninstallResult:
        pkg = self._repository.get_package(plugin_id)
        if pkg is None:
            return UninstallResult(
                plugin_id=plugin_id,
                errors=[f"Package '{plugin_id}' not found"],
            )
        result = await self._uninstaller.uninstall(
            pkg, self._repository.packages, remove_dependents,
        )
        if result.success:
            self._registry.mark_removed(plugin_id)
        return result

    def search_packages(self, query: str, category: Optional[str] = None,
                         tags: Optional[List[str]] = None,
                         page: int = 1, page_size: int = 20) -> SearchResult:
        return self._search.search(query, category, tags, page, page_size)

    def get_available_updates(self) -> List[PluginPackage]:
        return self._repository.get_available_updates(
            self._registry.get_installed_versions(),
        )

    def scan_repository(self) -> Dict[str, Any]:
        return self._repository.scan_local_repository()

    def health(self) -> MarketplaceHealth:
        stats = self._cache.get_statistics()
        installed = self._registry.get_installed()
        broken = [p for p in installed if p.is_broken]
        updates = self.get_available_updates()
        dep_issues = []
        graph = self._resolver.get_dependency_order(self._repository.packages)
        try:
            circular = self._resolver.check_circular(self._repository.packages)
            for cycle in circular:
                dep_issues.append(f"Circular dependency: {' -> '.join(cycle)}")
        except Exception:
            pass
        repo_stats = self._repository.get_statistics()

        details = []
        for pkg in installed:
            details.append({
                "plugin_id": pkg.id,
                "name": pkg.name,
                "version": pkg.version,
                "status": pkg.status.value,
                "has_update": pkg.id in [u.id for u in updates],
            })

        status = "healthy"
        if broken:
            status = "degraded"
        if dep_issues:
            status = "degraded"

        return MarketplaceHealth(
            overall_status=status,
            installed_count=len(installed),
            available_updates=len(updates),
            broken_packages=len(broken),
            dependency_issues=dep_issues,
            repository_status="synced" if repo_stats.get("last_sync") else "unknown",
            cache_hit_rate=stats.get("hit_rate", 0.0),
            cache_size_mb=stats.get("size_mb", 0.0),
            total_packages_available=repo_stats.get("total_packages", 0),
            last_repository_sync=repo_stats.get("last_sync"),
            package_details=details,
        )

    def resolve_dependencies(self, plugin_id: str) -> DependencyResolution:
        pkg = self._repository.get_package(plugin_id)
        if pkg is None:
            return DependencyResolution(
                success=False,
                missing_dependencies=[plugin_id],
            )
        return self._resolver.resolve(plugin_id, self._repository.packages,
                                       self._registry.get_installed_versions())

    def check_circular_dependencies(self) -> List[List[str]]:
        return self._resolver.check_circular(self._repository.packages)
