from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from loguru import logger
from app.kernel.health import HealthStatus, SubsystemHealth

class FridayHealthMonitor:
    """
    Centralized system health monitor where modules report their diagnostic status
    (Healthy, Warning, Degraded/Error, Offline/Unknown).
    """
    def __init__(self) -> None:
        self._statuses: Dict[str, SubsystemHealth] = {}

    def report_health(
        self,
        module_name: str,
        status: HealthStatus,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
        uptime_seconds: Optional[float] = None,
        dependencies: Optional[List[str]] = None,
        last_error: Optional[str] = None,
        ready: bool = True,
    ) -> None:
        """Subsystem callback reporting current status."""
        self._statuses[module_name] = SubsystemHealth(
            name=module_name,
            status=status,
            message=message,
            last_checked=datetime.now(timezone.utc),
            details=details or {},
            latency_ms=latency_ms,
            uptime_seconds=uptime_seconds,
            dependencies=dependencies or [],
            last_error=last_error,
            ready=ready,
        )
        logger.debug(f"Subsystem '{module_name}' health status: {status.value}")

    def get_health(self, module_name: str) -> SubsystemHealth:
        """Retrieves a module's diagnostic state."""
        if module_name in self._statuses:
            return self._statuses[module_name]
        return SubsystemHealth(
            name=module_name,
            status=HealthStatus.UNKNOWN,
            message="Subsystem has not reported health diagnostics yet.",
            ready=False,
        )

    def list_modules(self) -> List[str]:
        """Lists names of all modules currently monitored."""
        return list(self._statuses.keys())

    def consolidate_health(self) -> Dict[str, Any]:
        """Consolidates system-wide status sweeps into a unified dictionary."""
        overall_status = HealthStatus.HEALTHY
        overall_ready = True
        
        error_count = 0
        warning_count = 0
        
        subsystem_reports = {}
        for name, sub_health in self._statuses.items():
            subsystem_reports[name] = {
                "status": sub_health.status.value,
                "message": sub_health.message,
                "last_checked": sub_health.last_checked.isoformat(),
                "details": sub_health.details,
                "latency_ms": sub_health.latency_ms,
                "uptime_seconds": sub_health.uptime_seconds,
                "dependencies": sub_health.dependencies,
                "last_error": sub_health.last_error,
                "ready": sub_health.ready,
            }
            if sub_health.status == HealthStatus.ERROR:
                error_count += 1
            if not sub_health.ready:
                overall_ready = False
            if sub_health.status == HealthStatus.WARNING:
                warning_count += 1

        if error_count > 0:
            overall_status = HealthStatus.ERROR
        elif warning_count > 0:
            overall_status = HealthStatus.WARNING

        return {
            "status": overall_status.value,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ready": overall_ready,
            "subsystems": subsystem_reports,
            "summary": {
                "total": len(self._statuses),
                "healthy": sum(1 for s in self._statuses.values() if s.status == HealthStatus.HEALTHY),
                "warning": warning_count,
                "error": error_count,
            }
        }
