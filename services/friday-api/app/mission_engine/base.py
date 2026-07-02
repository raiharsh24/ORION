import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

class MissionState(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (MissionState.COMPLETED, MissionState.FAILED, MissionState.CANCELLED)

    @property
    def is_active(self) -> bool:
        return self == MissionState.RUNNING


class MissionPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Mission:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    state: MissionState = MissionState.PENDING
    priority: MissionPriority = MissionPriority.MEDIUM
    workflow_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds() * 1000


@dataclass
class MissionContext:
    mission_id: str = ""
    shared_data: Dict[str, Any] = field(default_factory=dict)
    workflow_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    node_outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class MissionCheckpoint:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str = ""
    mission_state: MissionState = MissionState.RUNNING
    completed_workflows: List[str] = field(default_factory=list)
    failed_workflows: List[str] = field(default_factory=list)
    running_workflow: Optional[str] = None
    context: Optional[MissionContext] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MissionProgress:
    total_workflows: int = 0
    completed: int = 0
    failed: int = 0
    running: int = 0
    remaining: int = 0
    skipped: int = 0

    @property
    def progress_pct(self) -> float:
        if self.total_workflows == 0:
            return 100.0
        done = self.completed + self.failed
        return (done / self.total_workflows) * 100.0


@dataclass
class MissionTelemetry:
    mission_duration_ms: float = 0.0
    completed_workflows: int = 0
    failed_workflows: int = 0
    remaining_workflows: int = 0
    checkpoint_count: int = 0
    resume_count: int = 0
    pause_count: int = 0
    cancel_count: int = 0


@dataclass
class MissionResult:
    mission_id: str = ""
    mission_name: str = ""
    status: MissionState = MissionState.PENDING
    workflow_results: Dict[str, Any] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    total_workflows: int = 0
    completed_workflows: int = 0
    failed_workflows: int = 0
    telemetry: MissionTelemetry = field(default_factory=MissionTelemetry)
    error: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    final_context: Optional[MissionContext] = None
