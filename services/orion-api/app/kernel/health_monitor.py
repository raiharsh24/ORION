from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from loguru import logger
from app.kernel.health import HealthStatus, SubsystemHealth

class OrionHealthMonitor:
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
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Subsystem callback reporting current status."""
        self._statuses[module_name] = SubsystemHealth(
            name=module_name,
            status=status,
            message=message,
            last_checked=datetime.now(timezone.utc),
            details=details or {}
        )
        logger.debug(f"Subsystem '{module_name}' health status: {status.value}")

    def get_health(self, module_name: str) -> SubsystemHealth:
        """Retrieves a module's diagnostic state."""
        if module_name in self._statuses:
            return self._statuses[module_name]
        return SubsystemHealth(
            name=module_name,
            status=HealthStatus.UNKNOWN,
            message="Subsystem has not reported health diagnostics yet."
        )

    def list_modules(self) -> List[str]:
        """Lists names of all modules currently monitored."""
        return list(self._statuses.keys())

    def consolidate_health(self) -> Dict[str, Any]:
        """Consolidates system-wide status sweeps into a unified dictionary."""
        overall_status = HealthStatus.HEALTHY
        
        error_count = 0
        warning_count = 0
        
        subsystem_reports = {}
        for name, sub_health in self._statuses.items():
            subsystem_reports[name] = {
                "status": sub_health.status.value,
                "message": sub_health.message,
                "last_checked": sub_health.last_checked.isoformat(),
                "details": sub_health.details
            }
            if sub_health.status == HealthStatus.ERROR:
                error_count += 1
            elif sub_health.status == HealthStatus.WARNING:
                warning_count += 1

        if error_count > 0:
            overall_status = HealthStatus.ERROR
        elif warning_count > 0:
            overall_status = HealthStatus.WARNING

        return {
            "status": overall_status.value,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "subsystems": subsystem_reports
        }
