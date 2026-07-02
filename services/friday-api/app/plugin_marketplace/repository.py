import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, MarketplaceConfig, PackageDependency,
)
from app.plugin_marketplace.manifest import parse_package_manifest
from app.plugin_marketplace.events import RepositoryUpdated


class RepositoryManager:
    def __init__(
        self,
        config: MarketplaceConfig,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._packages: Dict[str, PluginPackage] = {}
        self._index: Dict[str, PluginPackage] = {}
        self._categories: Dict[str, List[str]] = {}
        self._tags: Dict[str, List[str]] = {}
        self._featured: List[str] = []
        self._last_sync: Optional[str] = None

    @property
    def packages(self) -> Dict[str, PluginPackage]:
        return self._packages

    def scan_local_repository(self) -> Dict[str, Any]:
        base = Path(self._config.local_repository_path)
        if not base.exists():
            return {"added": 0, "removed": 0, "total": 0}

        added = 0
        found_ids = set()

        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            manifest_file = entry / "plugin.json"
            if not manifest_file.exists():
                manifest_file = entry / "manifest.json"
            if not manifest_file.exists():
                continue
            pkg = parse_package_manifest(manifest_file)
            if pkg is None:
                continue
            pkg.install_path = str(entry)
            pkg.status = None
            found_ids.add(pkg.id)
            if pkg.id not in self._packages:
                self._packages[pkg.id] = pkg
                self._index_package(pkg)
                added += 1
            else:
                existing = self._packages[pkg.id]
                if _version_greater(pkg.version, existing.version):
                    self._packages[pkg.id] = pkg
                    self._index_package(pkg)
                    added += 1

        removed = 0
        for pid in list(self._packages.keys()):
            if pid not in found_ids and self._packages[pid].source == "local":
                del self._packages[pid]
                removed += 1

        self._last_sync = datetime.now(timezone.utc).isoformat()
        total = len(self._packages)
        self._publish(RepositoryUpdated(
            repository="local",
            added=added, removed=removed, total=total,
        ))
        return {"added": added, "removed": removed, "total": total}

    def add_package(self, pkg: PluginPackage) -> None:
        self._packages[pkg.id] = pkg
        self._index_package(pkg)

    def remove_package(self, plugin_id: str) -> bool:
        if plugin_id in self._packages:
            self._remove_from_index(plugin_id)
            del self._packages[plugin_id]
            return True
        return False

    def get_package(self, plugin_id: str) -> Optional[PluginPackage]:
        return self._packages.get(plugin_id)

    def get_all_packages(self) -> List[PluginPackage]:
        return list(self._packages.values())

    def get_installed(self, installed_ids: Set[str]) -> List[PluginPackage]:
        return [p for p in self._packages.values() if p.id in installed_ids]

    def get_available_updates(self, installed: Dict[str, str]) -> List[PluginPackage]:
        updates = []
        for pid, current_version in installed.items():
            pkg = self._packages.get(pid)
            if pkg and _version_greater(pkg.version, current_version):
                updates.append(pkg)
        return updates

    def get_by_category(self, category: str) -> List[PluginPackage]:
        ids = self._categories.get(category.lower(), [])
        return [self._packages[pid] for pid in ids if pid in self._packages]

    def get_featured(self) -> List[PluginPackage]:
        ids = self._config.featured_plugin_ids or self._featured
        return [self._packages[pid] for pid in ids if pid in self._packages]

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_packages": len(self._packages),
            "categories": len(self._categories),
            "tags": len(self._tags),
            "featured": len(self._featured),
            "last_sync": self._last_sync,
        }

    def _index_package(self, pkg: PluginPackage) -> None:
        for cat in pkg.categories:
            c = cat.lower()
            if c not in self._categories:
                self._categories[c] = []
            if pkg.id not in self._categories[c]:
                self._categories[c].append(pkg.id)
        for tag in pkg.tags:
            t = tag.lower()
            if t not in self._tags:
                self._tags[t] = []
            if pkg.id not in self._tags[t]:
                self._tags[t].append(pkg.id)
        if pkg.featured and pkg.id not in self._featured:
            self._featured.append(pkg.id)

    def _remove_from_index(self, plugin_id: str) -> None:
        for cat in list(self._categories.keys()):
            self._categories[cat] = [pid for pid in self._categories[cat]
                                      if pid != plugin_id]
            if not self._categories[cat]:
                del self._categories[cat]
        for tag in list(self._tags.keys()):
            self._tags[tag] = [pid for pid in self._tags[tag]
                                if pid != plugin_id]
            if not self._tags[tag]:
                del self._tags[tag]
        self._featured = [pid for pid in self._featured if pid != plugin_id]

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


def _version_greater(v1: str, v2: str) -> bool:
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]
    for a, b in zip(parts1, parts2):
        if a > b:
            return True
        if a < b:
            return False
    return len(parts1) > len(parts2)
