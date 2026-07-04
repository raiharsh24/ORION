import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from app.runtime.base import Mission as _RuntimeMission


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


class Mission:
    """
    Engine V2-compatible Mission wrapping the canonical runtime Mission.
    Preserves the MissionState/MissionPriority enum interface while
    delegating storage to the canonical dataclass.
    """
    def __init__(
        self,
        id: str = "",
        name: str = "",
        description: str = "",
        state: MissionState = MissionState.PENDING,
        priority: MissionPriority = MissionPriority.MEDIUM,
        workflow_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> None:
        self._m = _RuntimeMission(
            mission_id=id or str(uuid.uuid4()),
            name=name,
            description=description,
            status=state.value if isinstance(state, MissionState) else str(state).lower(),
            priority=priority.value if isinstance(priority, MissionPriority) else str(priority).lower(),
            workflow_ids=workflow_ids or [],
            metadata=metadata or {},
            created_at=created_at or datetime.now(timezone.utc),
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )

    @property
    def id(self) -> str:
        return self._m.mission_id

    @id.setter
    def id(self, value: str) -> None:
        self._m.mission_id = value

    @property
    def name(self) -> str:
        return self._m.name

    @name.setter
    def name(self, value: str) -> None:
        self._m.name = value

    @property
    def description(self) -> str:
        return self._m.description

    @description.setter
    def description(self, value: str) -> None:
        self._m.description = value

    @property
    def state(self) -> MissionState:
        return MissionState(self._m.status)

    @state.setter
    def state(self, value: MissionState) -> None:
        if isinstance(value, MissionState):
            self._m.status = value.value
        else:
            self._m.status = str(value).lower()

    @property
    def priority(self) -> MissionPriority:
        return MissionPriority(self._m.priority)

    @priority.setter
    def priority(self, value: MissionPriority) -> None:
        if isinstance(value, MissionPriority):
            self._m.priority = value.value
        else:
            self._m.priority = str(value).lower()

    @property
    def workflow_ids(self) -> List[str]:
        return self._m.workflow_ids

    @workflow_ids.setter
    def workflow_ids(self, value: List[str]) -> None:
        self._m.workflow_ids = value

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._m.metadata

    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        self._m.metadata = value

    @property
    def created_at(self) -> datetime:
        return self._m.created_at

    @created_at.setter
    def created_at(self, value: datetime) -> None:
        self._m.created_at = value

    @property
    def started_at(self) -> Optional[datetime]:
        return self._m.started_at

    @started_at.setter
    def started_at(self, value: Optional[datetime]) -> None:
        self._m.started_at = value

    @property
    def completed_at(self) -> Optional[datetime]:
        return self._m.completed_at

    @completed_at.setter
    def completed_at(self, value: Optional[datetime]) -> None:
        self._m.completed_at = value

    @property
    def error(self) -> Optional[str]:
        return self._m.error

    @error.setter
    def error(self, value: Optional[str]) -> None:
        self._m.error = value

    @property
    def duration_ms(self) -> float:
        if self._m.started_at is None:
            return 0.0
        end = self._m.completed_at or datetime.now(timezone.utc)
        return (end - self._m.started_at).total_seconds() * 1000


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
