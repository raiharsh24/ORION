from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone

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
    Represents a high-level task goal composed of multiple workflows.
    Maintains the status, priority, type, progress tracking, and metadata for a mission run.
    """
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        priority: MissionPriority = MissionPriority.NORMAL,
        type: MissionType = MissionType.USER_DEFINED,
        workflow_id: Optional[str] = None,
        current_step: Optional[str] = None,
        progress: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.status: MissionStatus = MissionStatus.CREATED
        self.priority: MissionPriority = priority
        self.type: MissionType = type
        self.created_at: datetime = created_at or datetime.now(timezone.utc)
        self.updated_at: datetime = updated_at or datetime.now(timezone.utc)
        self.workflow_id: Optional[str] = workflow_id
        self.current_step: Optional[str] = current_step
        self.progress: float = progress
        self.metadata: Dict[str, Any] = metadata or {}
