from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class RuntimeHealth:
    status: str = "healthy"
    running_missions: int = 0
    queued_missions: int = 0
    paused_missions: int = 0
    completed_missions: int = 0
    failed_missions: int = 0
    average_runtime_ms: float = 0.0
    total_retries: int = 0
    total_recoveries: int = 0
    recovery_success_rate: float = 1.0
    uptime_hours: float = 0.0
    max_concurrent: int = 4
    success_rate: float = 1.0
    dispatcher_available: bool = True
    executor_available: bool = True
    supervisor_available: bool = True
    checked_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "running_missions": self.running_missions,
            "queued_missions": self.queued_missions,
            "paused_missions": self.paused_missions,
            "completed_missions": self.completed_missions,
            "failed_missions": self.failed_missions,
            "average_runtime_ms": self.average_runtime_ms,
            "total_retries": self.total_retries,
            "total_recoveries": self.total_recoveries,
            "recovery_success_rate": self.recovery_success_rate,
            "uptime_hours": self.uptime_hours,
            "max_concurrent": self.max_concurrent,
            "success_rate": self.success_rate,
            "dispatcher_available": self.dispatcher_available,
            "executor_available": self.executor_available,
            "supervisor_available": self.supervisor_available,
            "checked_at": (self.checked_at or datetime.now(timezone.utc)).isoformat(),
        }
