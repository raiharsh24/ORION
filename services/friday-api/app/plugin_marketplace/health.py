from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MarketplaceHealth:
    overall_status: str = "unknown"
    installed_count: int = 0
    available_updates: int = 0
    broken_packages: int = 0
    dependency_issues: List[str] = field(default_factory=list)
    repository_status: str = "unknown"
    cache_hit_rate: float = 0.0
    cache_size_mb: float = 0.0
    total_packages_available: int = 0
    last_repository_sync: Optional[str] = None
    package_details: List[Dict[str, Any]] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "installed_count": self.installed_count,
            "available_updates": self.available_updates,
            "broken_packages": self.broken_packages,
            "dependency_issues": self.dependency_issues,
            "repository_status": self.repository_status,
            "cache_hit_rate": round(self.cache_hit_rate, 2),
            "cache_size_mb": round(self.cache_size_mb, 2),
            "total_packages_available": self.total_packages_available,
            "last_repository_sync": self.last_repository_sync,
            "package_details": self.package_details,
            "checked_at": self.checked_at.isoformat(),
        }
