import time
import json
import shutil
from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, PackageStatus, MarketplaceConfig,
    InstallResult, CacheEntry,
)
from app.plugin_marketplace.events import (
    PluginInstalled, PackageDownloaded, PackageVerified,
)
from app.plugin_marketplace.resolver import DependencyResolver
from app.plugin_marketplace.cache import PackageCache
from app.plugin_marketplace.package import PackageIntegrity
from app.plugin_runtime.runtime import PluginRuntime


class PackageInstaller:
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

    async def install(self, pkg: PluginPackage,
                       packages: Dict[str, PluginPackage],
                       force: bool = False) -> InstallResult:
        result = InstallResult(
            plugin_id=pkg.id, version=pkg.version,
        )
        if pkg.is_installed and not force:
            result.errors.append(f"Plugin '{pkg.id}' is already installed")
            return result

        resolution = self._resolver.resolve(pkg.id, packages)
        if not resolution.success:
            result.errors = resolution.messages
            return result

        pkg.status = PackageStatus.INSTALLING
        installed_deps = []

        try:
            for dep_id in resolution.order:
                if dep_id == pkg.id:
                    continue
                dep_pkg = packages.get(dep_id)
                if dep_pkg and not dep_pkg.is_installed:
                    dep_result = await self.install(dep_pkg, packages)
                    if dep_result.success:
                        installed_deps.append(dep_id)
                    else:
                        result.errors.extend(dep_result.errors)
                        return result

            install_dir = Path(self._config.local_repository_path) / pkg.id
            install_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = install_dir / "plugin.json"
            from app.plugin_marketplace.manifest import manifest_to_dict
            manifest_path.write_text(json.dumps(manifest_to_dict(pkg), indent=2))

            pkg.install_path = str(install_dir)
            pkg.installed_at = datetime.now(timezone.utc)
            pkg.status = PackageStatus.INSTALLED

            self._publish(PluginInstalled(
                plugin_id=pkg.id, name=pkg.name, version=pkg.version,
            ))
            result.success = True
            result.installed_dependencies = installed_deps
            logger.info(f"Installed plugin '{pkg.id}' v{pkg.version}")

        except Exception as e:
            pkg.status = PackageStatus.BROKEN
            result.errors.append(str(e))
            logger.error(f"Failed to install plugin '{pkg.id}': {e}")

        return result

    async def install_from_path(self, path: str,
                                  packages: Dict[str, PluginPackage]) -> InstallResult:
        from app.plugin_marketplace.package import PackageBuilder
        pkg = PackageBuilder.from_directory(path)
        if pkg is None:
            return InstallResult(
                plugin_id="", errors=[f"Invalid package at '{path}'"],
            )
        return await self.install(pkg, packages)

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
