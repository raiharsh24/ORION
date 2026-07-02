from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


@dataclass
class PlanningHealth:
    status: str = "healthy"
    plans_generated: int = 0
    average_planning_time_ms: float = 0.0
    validation_failures: int = 0
    cache_hits: int = 0
    simulation_accuracy: float = 0.0
    total_goals: int = 0
    active_goals: int = 0
    plans_cached: int = 0
    template_count: int = 0
    checked_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "plans_generated": self.plans_generated,
            "average_planning_time_ms": self.average_planning_time_ms,
            "validation_failures": self.validation_failures,
            "cache_hits": self.cache_hits,
            "simulation_accuracy": self.simulation_accuracy,
            "total_goals": self.total_goals,
            "active_goals": self.active_goals,
            "plans_cached": self.plans_cached,
            "template_count": self.template_count,
            "checked_at": (self.checked_at or datetime.now(timezone.utc)).isoformat(),
        }
