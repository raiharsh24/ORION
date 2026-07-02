from typing import Dict, List, Optional, Set
from app.plugin_marketplace.base import (
    PluginPackage, PackageStatus,
)


class MarketplaceRegistry:
    def __init__(self) -> None:
        self._packages: Dict[str, PluginPackage] = {}
        self._installed: Dict[str, str] = {}

    def register(self, pkg: PluginPackage) -> None:
        self._packages[pkg.id] = pkg

    def unregister(self, plugin_id: str) -> bool:
        return self._packages.pop(plugin_id, None) is not None

    def get(self, plugin_id: str) -> Optional[PluginPackage]:
        return self._packages.get(plugin_id)

    def mark_installed(self, plugin_id: str, version: str) -> None:
        self._installed[plugin_id] = version
        pkg = self._packages.get(plugin_id)
        if pkg:
            pkg.status = PackageStatus.INSTALLED

    def mark_removed(self, plugin_id: str) -> None:
        self._installed.pop(plugin_id, None)
        pkg = self._packages.get(plugin_id)
        if pkg:
            pkg.status = PackageStatus.REMOVED

    def mark_broken(self, plugin_id: str) -> None:
        pkg = self._packages.get(plugin_id)
        if pkg:
            pkg.status = PackageStatus.BROKEN

    def is_installed(self, plugin_id: str) -> bool:
        return plugin_id in self._installed

    def get_all(self) -> List[PluginPackage]:
        return list(self._packages.values())

    def get_installed(self) -> List[PluginPackage]:
        return [p for p in self._packages.values()
                if p.id in self._installed]

    def get_installed_ids(self) -> Set[str]:
        return set(self._installed.keys())

    def get_installed_versions(self) -> Dict[str, str]:
        return dict(self._installed)

    def list_all_ids(self) -> List[str]:
        return list(self._packages.keys())
