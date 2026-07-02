import shutil
from pathlib import Path
from typing import Optional, Any, List
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, PackageStatus, MarketplaceConfig, UninstallResult,
)
from app.plugin_marketplace.events import PluginRemoved
from app.plugin_marketplace.resolver import DependencyResolver
from app.plugin_marketplace.cache import PackageCache
from app.plugin_runtime.runtime import PluginRuntime


class PackageUninstaller:
    def __init__(
        self,
        runtime: PluginRuntime,
        resolver: DependencyResolver,
        cache: PackageCache,
        config: MarketplaceConfig,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._runtime = runtime
        self._resolver = resolver
        self._cache = cache
        self._config = config
        self._event_bus = event_bus

    async def uninstall(self, pkg: PluginPackage,
                          packages: dict,
                          remove_dependents: bool = False) -> UninstallResult:
        result = UninstallResult(plugin_id=pkg.id)
        if not pkg.is_installed:
            result.errors.append(f"Plugin '{pkg.id}' is not installed")
            return result

        pkg.status = PackageStatus.REMOVING
        removed_deps = []

        try:
            if remove_dependents:
                for pid, other in list(packages.items()):
                    if pid != pkg.id and other.is_installed:
                        if pkg.id in [d.plugin_id for d in other.dependencies]:
                            dep_result = await self.uninstall(
                                other, packages, False,
                            )
                            removed_deps.append(pid)
                            result.removed_dependents.append(pid)

            try:
                await self._runtime.unload_plugin(pkg.id)
            except Exception:
                pass

            install_dir = Path(self._config.local_repository_path) / pkg.id
            if install_dir.exists():
                shutil.rmtree(install_dir)

            self._cache.remove(pkg.id, pkg.version)
            pkg.install_path = None
            pkg.status = PackageStatus.REMOVED

            self._publish(PluginRemoved(
                plugin_id=pkg.id, name=pkg.name, version=pkg.version,
            ))
            result.success = True
            logger.info(f"Uninstalled plugin '{pkg.id}' v{pkg.version}")

        except Exception as e:
            pkg.status = PackageStatus.BROKEN
            result.errors.append(str(e))
            logger.error(f"Failed to uninstall plugin '{pkg.id}': {e}")

        return result

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    pass
            except Exception:
                pass
