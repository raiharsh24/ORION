from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.runtime.base import Mission as _RuntimeMission


class MissionStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MissionType(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    AUTOMATION = "AUTOMATION"
    KNOWLEDGE = "KNOWLEDGE"
    SYSTEM = "SYSTEM"
    USER_DEFINED = "USER_DEFINED"


class Mission:
    """
    Legacy-compatible Mission wrapping the canonical runtime Mission.
    Preserves the enum-based interface (MissionStatus, MissionPriority, MissionType)
    while delegating storage to the canonical dataclass.
    """
    def __init__(
        self,
        id: str,
        name: str = "",
        description: str = "",
        priority: MissionPriority = MissionPriority.NORMAL,
        type: MissionType = MissionType.USER_DEFINED,
        workflow_id: Optional[str] = None,
        current_step: Optional[str] = None,
        progress: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ) -> None:
        self._m = _RuntimeMission(
            mission_id=id,
            name=name,
            description=description,
            status="CREATED",
            priority=priority.value.lower() if isinstance(priority, MissionPriority) else str(priority).lower(),
            mission_type=type.value.lower() if isinstance(type, MissionType) else str(type).lower(),
            workflow_ids=[workflow_id] if workflow_id else [],
            current_step=current_step,
            progress=progress,
            metadata=metadata or {},
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc),
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
    def status(self) -> MissionStatus:
        return MissionStatus(self._m.status)

    @status.setter
    def status(self, value: MissionStatus) -> None:
        if isinstance(value, MissionStatus):
            self._m.status = value.value
        else:
            self._m.status = str(value).upper()

    @property
    def priority(self) -> MissionPriority:
        return MissionPriority(self._m.priority.upper())

    @priority.setter
    def priority(self, value: MissionPriority) -> None:
        if isinstance(value, MissionPriority):
            self._m.priority = value.value.lower()
        else:
            self._m.priority = str(value).lower()

    @property
    def type(self) -> MissionType:
        return MissionType(self._m.mission_type.upper())

    @type.setter
    def type(self, value: MissionType) -> None:
        if isinstance(value, MissionType):
            self._m.mission_type = value.value.lower()
        else:
            self._m.mission_type = str(value).lower()

    @property
    def workflow_id(self) -> Optional[str]:
        return self._m.workflow_ids[0] if self._m.workflow_ids else None

    @workflow_id.setter
    def workflow_id(self, value: Optional[str]) -> None:
        if value is not None:
            self._m.workflow_ids = [value]
        else:
            self._m.workflow_ids = []

    @property
    def current_step(self) -> Optional[str]:
        return self._m.current_step

    @current_step.setter
    def current_step(self, value: Optional[str]) -> None:
        self._m.current_step = value

    @property
    def progress(self) -> float:
        return self._m.progress

    @progress.setter
    def progress(self, value: float) -> None:
        self._m.progress = value

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
    def updated_at(self) -> datetime:
        return self._m.updated_at

    @updated_at.setter
    def updated_at(self, value: datetime) -> None:
        self._m.updated_at = value
