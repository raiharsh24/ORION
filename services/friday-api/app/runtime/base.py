from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


@dataclass
class MissionStage:
    name: str
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0


@dataclass
class Mission:
    mission_id: str
    user_request: str = ""
    intent: str = ""
    status: str = "created"
    stages: List[MissionStage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    plan_id: Optional[str] = None
    goal_ids: List[str] = field(default_factory=list)
    assigned_agents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    name: str = ""
    description: str = ""
    workflow_ids: List[str] = field(default_factory=list)
    current_step: Optional[str] = None
    progress: float = 0.0
    started_at: Optional[datetime] = None
    priority: str = "normal"
    mission_type: str = "user_defined"

    @property
    def id(self) -> str:
        return self.mission_id

    def add_stage(self, name: str) -> MissionStage:
        stage = MissionStage(name=name, status="running",
                             started_at=datetime.now(timezone.utc))
        self.stages.append(stage)
        self.updated_at = datetime.now(timezone.utc)
        return stage

    def complete_stage(self, name: str, error: Optional[str] = None) -> None:
        for stage in self.stages:
            if stage.name == name:
                stage.status = "failed" if error else "completed"
                stage.completed_at = datetime.now(timezone.utc)
                stage.error = error
                break
        self.updated_at = datetime.now(timezone.utc)

    def set_status(self, status: str) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if status in ("completed", "failed", "archived"):
            self.completed_at = datetime.now(timezone.utc)

    @property
    def total_duration_ms(self) -> float:
        if self.created_at and self.completed_at:
            return (self.completed_at - self.created_at).total_seconds() * 1000
        return 0.0

    @property
    def current_stage(self) -> Optional[str]:
        for stage in reversed(self.stages):
            if stage.status == "running":
                return stage.name
        return None


@dataclass
class ExecutionResult:
    success: bool
    mission_id: str
    output: Any = None
    error: Optional[str] = None
    stages_completed: int = 0
    total_duration_ms: float = 0.0
    telemetry: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryAction:
    action_type: str
    target: str
    reason: str
    status: str = "pending"
    result: Optional[str] = None
