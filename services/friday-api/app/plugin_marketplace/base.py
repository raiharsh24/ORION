from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class PackageStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATING = "updating"
    ROLLING_BACK = "rolling_back"
    REMOVING = "removing"
    REMOVED = "removed"
    BROKEN = "broken"
    CONFLICTED = "conflicted"


@dataclass
class PackageDependency:
    plugin_id: str
    version_constraint: str = ">=1.0.0"
    optional: bool = False


@dataclass
class PluginPackage:
    id: str
    name: str
    version: str
    author: str = ""
    license: str = ""
    homepage: str = ""
    documentation: str = ""
    description: str = ""
    min_friday_version: str = ""
    max_friday_version: str = ""
    dependencies: List[PackageDependency] = field(default_factory=list)
    optional_dependencies: List[PackageDependency] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    entry_point: str = ""
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    install_path: Optional[str] = None
    installed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    integrity_hash: str = ""
    package_size: int = 0
    source: str = "local"
    status: PackageStatus = PackageStatus.NOT_INSTALLED
    rating: float = 0.0
    download_count: int = 0
    featured: bool = False
    icon_url: str = ""
    screenshots: List[str] = field(default_factory=list)

    @property
    def is_installed(self) -> bool:
        return self.status == PackageStatus.INSTALLED

    @property
    def needs_update(self) -> bool:
        return False

    @property
    def is_broken(self) -> bool:
        return self.status == PackageStatus.BROKEN


@dataclass
class MarketplaceConfig:
    local_repository_path: str = "./plugins"
    cache_path: str = "./.plugin_cache"
    max_cache_size_mb: float = 500.0
    verify_integrity: bool = True
    auto_resolve_dependencies: bool = True
    allow_downgrade: bool = False
    backup_on_update: bool = True
    max_backup_versions: int = 3
    repository_url: str = ""
    featured_plugin_ids: List[str] = field(default_factory=list)


@dataclass
class DependencyGraph:
    nodes: Dict[str, 'DependencyNode'] = field(default_factory=dict)


@dataclass
class DependencyNode:
    plugin_id: str
    version: str = ""
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    resolved: bool = False
    visited: bool = False


@dataclass
class DependencyResolution:
    success: bool = False
    order: List[str] = field(default_factory=list)
    circular_dependencies: List[List[str]] = field(default_factory=list)
    missing_dependencies: List[str] = field(default_factory=list)
    version_conflicts: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)


@dataclass
class PackageIntegrityInfo:
    hash_algorithm: str = "sha256"
    expected_hash: str = ""
    actual_hash: str = ""
    package_size: int = 0
    signature_valid: bool = False
    manifest_valid: bool = False
    verified: bool = False
    errors: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verified and not self.errors


@dataclass
class CacheEntry:
    plugin_id: str
    version: str
    cache_path: str
    cached_at: datetime
    size_bytes: int
    integrity_hash: str
    access_count: int = 0
    last_accessed: Optional[datetime] = None


@dataclass
class SearchResult:
    query: str
    total: int = 0
    results: List[PluginPackage] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


@dataclass
class InstallResult:
    success: bool = False
    plugin_id: str = ""
    version: str = ""
    errors: List[str] = field(default_factory=list)
    installed_dependencies: List[str] = field(default_factory=list)
    rollback_available: bool = False
    rollback_version: str = ""


@dataclass
class UpdateResult:
    success: bool = False
    plugin_id: str = ""
    old_version: str = ""
    new_version: str = ""
    errors: List[str] = field(default_factory=list)
    rollback_performed: bool = False


@dataclass
class UninstallResult:
    success: bool = False
    plugin_id: str = ""
    errors: List[str] = field(default_factory=list)
    removed_dependents: List[str] = field(default_factory=list)
