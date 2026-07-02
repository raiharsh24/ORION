import time
import json
import shutil
from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, PackageStatus, MarketplaceConfig,
    UpdateResult,
)
from app.plugin_marketplace.events import (
    PluginUpdated, PluginRollback,
)
from app.plugin_marketplace.resolver import DependencyResolver
from app.plugin_marketplace.cache import PackageCache
from app.plugin_marketplace.manifest import manifest_to_dict
from app.plugin_runtime.runtime import PluginRuntime


class PackageUpdater:
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
        self._backups: Dict[str, List[Dict]] = {}

    async def update(self, pkg: PluginPackage,
                      new_pkg: PluginPackage,
                      packages: Dict[str, PluginPackage]) -> UpdateResult:
        result = UpdateResult(
            plugin_id=pkg.id,
            old_version=pkg.version,
            new_version=new_pkg.version,
        )
        if not pkg.is_installed:
            result.errors.append(f"Plugin '{pkg.id}' is not installed")
            return result

        if pkg.version == new_pkg.version:
            result.errors.append(f"Plugin '{pkg.id}' is already at version {pkg.version}")
            return result

        pkg.status = PackageStatus.UPDATING

        try:
            if self._config.backup_on_update:
                self._backup(pkg)

            try:
                await self._runtime.unload_plugin(pkg.id)
            except Exception:
                pass

            install_dir = Path(self._config.local_repository_path) / pkg.id
            install_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = install_dir / "plugin.json"
            manifest_path.write_text(json.dumps(manifest_to_dict(new_pkg), indent=2))

            old_version = pkg.version
            pkg.version = new_pkg.version
            pkg.install_path = str(install_dir)
            pkg.updated_at = datetime.now(timezone.utc)
            pkg.status = PackageStatus.INSTALLED

            self._publish(PluginUpdated(
                plugin_id=pkg.id, name=pkg.name,
                old_version=old_version, new_version=pkg.version,
            ))
            result.success = True
            logger.info(f"Updated plugin '{pkg.id}' {old_version} -> {pkg.version}")

        except Exception as e:
            pkg.status = PackageStatus.BROKEN
            result.errors.append(str(e))
            if self._config.backup_on_update:
                await self.rollback(pkg)
                result.rollback_performed = True

        return result

    async def rollback(self, pkg: PluginPackage) -> UpdateResult:
        old_version = pkg.version
        backups = self._backups.pop(pkg.id, [])
        if not backups:
            return UpdateResult(
                plugin_id=pkg.id,
                old_version=old_version,
                new_version=old_version,
                errors=["No backup available"],
            )
        backup = backups[-1]
        pkg.status = PackageStatus.ROLLING_BACK

        try:
            install_dir = Path(self._config.local_repository_path) / pkg.id
            install_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = install_dir / "plugin.json"
            manifest_path.write_text(json.dumps(backup["manifest"], indent=2))

            rollback_version = backup["version"]
            pkg.version = rollback_version
            pkg.status = PackageStatus.INSTALLED

            self._publish(PluginRollback(
                plugin_id=pkg.id, name=pkg.name,
                from_version=old_version, to_version=rollback_version,
            ))
            result = UpdateResult(
                success=True,
                plugin_id=pkg.id,
                old_version=old_version,
                new_version=rollback_version,
                rollback_performed=True,
            )
            logger.info(f"Rolled back plugin '{pkg.id}' {old_version} -> {rollback_version}")
            return result

        except Exception as e:
            pkg.status = PackageStatus.BROKEN
            return UpdateResult(
                plugin_id=pkg.id,
                old_version=old_version,
                new_version=pkg.version,
                errors=[str(e)],
            )

    def _backup(self, pkg: PluginPackage) -> None:
        if pkg.id not in self._backups:
            self._backups[pkg.id] = []
        backup = {
            "version": pkg.version,
            "manifest": manifest_to_dict(pkg),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._backups[pkg.id].append(backup)
        while len(self._backups[pkg.id]) > self._config.max_backup_versions:
            self._backups[pkg.id].pop(0)

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
