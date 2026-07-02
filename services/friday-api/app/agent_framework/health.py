from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


@dataclass
class CoordinatorHealth:
    status: str = "healthy"
    queue_size: int = 0
    active_tasks: int = 0
    resources_allocated: int = 0


@dataclass
class DelegationHealth:
    status: str = "healthy"
    total_tasks: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0


@dataclass
class BlackboardHealth:
    status: str = "healthy"
    entries: int = 0
    locked_keys: int = 0
    working_memory_entries: int = 0


@dataclass
class PersistenceHealth:
    status: str = "healthy"
    has_checkpoint: bool = False
    stored_agents: int = 0
    total_files: int = 0


@dataclass
class RecoveryHealth:
    status: str = "healthy"
    last_recovery: Optional[str] = None
    total_recoveries: int = 0


@dataclass
class AgentFrameworkHealth:
    overall_status: str = "healthy"
    running_agents: int = 0
    idle_agents: int = 0
    failed_agents: int = 0
    planning_agents: int = 0
    waiting_agents: int = 0
    paused_agents: int = 0
    completed_agents: int = 0
    cancelled_agents: int = 0
    total_agents: int = 0
    queue_size: int = 0
    pending_tasks: int = 0
    average_execution_time_ms: float = 0.0
    agents_with_context: int = 0
    bus_subscribers: int = 0
    bus_pending_responses: int = 0
    scheduled_entries: int = 0
    checked_at: Optional[datetime] = None
    agent_details: List[Dict[str, Any]] = field(default_factory=list)
    coordinator: Optional[CoordinatorHealth] = None
    delegation: Optional[DelegationHealth] = None
    blackboard: Optional[BlackboardHealth] = None
    persistence: Optional[PersistenceHealth] = None
    recovery: Optional[RecoveryHealth] = None

    def to_dict(self) -> dict:
        d = {
            "overall_status": self.overall_status,
            "running_agents": self.running_agents,
            "idle_agents": self.idle_agents,
            "failed_agents": self.failed_agents,
            "planning_agents": self.planning_agents,
            "waiting_agents": self.waiting_agents,
            "paused_agents": self.paused_agents,
            "completed_agents": self.completed_agents,
            "cancelled_agents": self.cancelled_agents,
            "total_agents": self.total_agents,
            "queue_size": self.queue_size,
            "pending_tasks": self.pending_tasks,
            "average_execution_time_ms": self.average_execution_time_ms,
            "agents_with_context": self.agents_with_context,
            "bus_subscribers": self.bus_subscribers,
            "bus_pending_responses": self.bus_pending_responses,
            "scheduled_entries": self.scheduled_entries,
            "checked_at": (self.checked_at or datetime.now(timezone.utc)).isoformat(),
            "agent_details": self.agent_details,
        }
        if self.coordinator:
            d["coordinator"] = {
                "status": self.coordinator.status,
                "queue_size": self.coordinator.queue_size,
                "active_tasks": self.coordinator.active_tasks,
                "resources_allocated": self.coordinator.resources_allocated,
            }
        if self.delegation:
            d["delegation"] = {
                "status": self.delegation.status,
                "total_tasks": self.delegation.total_tasks,
                "pending": self.delegation.pending,
                "running": self.delegation.running,
                "completed": self.delegation.completed,
                "failed": self.delegation.failed,
            }
        if self.blackboard:
            d["blackboard"] = {
                "status": self.blackboard.status,
                "entries": self.blackboard.entries,
                "locked_keys": self.blackboard.locked_keys,
                "working_memory_entries": self.blackboard.working_memory_entries,
            }
        if self.persistence:
            d["persistence"] = {
                "status": self.persistence.status,
                "has_checkpoint": self.persistence.has_checkpoint,
                "stored_agents": self.persistence.stored_agents,
                "total_files": self.persistence.total_files,
            }
        if self.recovery:
            d["recovery"] = {
                "status": self.recovery.status,
                "last_recovery": self.recovery.last_recovery,
                "total_recoveries": self.recovery.total_recoveries,
            }
        return d
