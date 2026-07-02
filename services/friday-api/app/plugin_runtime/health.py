from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PluginRuntimeHealth:
    overall_status: str = "unknown"
    total_plugins: int = 0
    running_plugins: int = 0
    failed_plugins: int = 0
    suspended_plugins: int = 0
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_reloads: int = 0
    sandbox_violations: int = 0
    average_load_time_ms: float = 0.0
    peak_plugins: int = 0
    uptime_seconds: float = 0.0
    last_crash: Optional[Dict[str, Any]] = None
    plugin_details: List[Dict[str, Any]] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "total_plugins": self.total_plugins,
            "running_plugins": self.running_plugins,
            "failed_plugins": self.failed_plugins,
            "suspended_plugins": self.suspended_plugins,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "total_reloads": self.total_reloads,
            "sandbox_violations": self.sandbox_violations,
            "average_load_time_ms": round(self.average_load_time_ms, 2),
            "peak_plugins": self.peak_plugins,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "last_crash": self.last_crash,
            "plugin_details": self.plugin_details,
            "checked_at": self.checked_at.isoformat(),
        }
