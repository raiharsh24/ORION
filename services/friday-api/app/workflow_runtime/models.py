from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime, timezone


class RuntimeStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class RuntimeWorkflowStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ScheduleType(str, Enum):
    ONCE = "ONCE"
    DELAYED = "DELAYED"
    INTERVAL = "INTERVAL"
    CRON = "CRON"


class RetryPolicy(BaseModel):
    max_retries: int = 0
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retryable_errors: List[str] = Field(default_factory=list)


class ScheduleConfig(BaseModel):
    schedule_type: ScheduleType = ScheduleType.ONCE
    delay_seconds: Optional[float] = None
    interval_seconds: Optional[float] = None
    cron_expression: Optional[str] = None
    max_runs: Optional[int] = None
    next_run: Optional[datetime] = None


class RuntimeStep(BaseModel):
    step_id: str
    name: str
    step_type: str
    input: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout: Optional[float] = None
    status: RuntimeStepStatus = RuntimeStepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    parallel_group: Optional[str] = None


class RuntimeWorkflow(BaseModel):
    workflow_id: str
    name: str
    description: str = ""
    steps: Dict[str, RuntimeStep] = Field(default_factory=dict)
    status: RuntimeWorkflowStatus = RuntimeWorkflowStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    schedule: Optional[ScheduleConfig] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_plan: Optional[Dict[str, Any]] = None

    def get_runnable_steps(self) -> List[RuntimeStep]:
        pending = [s for s in self.steps.values() if s.status == RuntimeStepStatus.PENDING]
        result = []
        for step in pending:
            deps_met = all(
                self.steps[d].status == RuntimeStepStatus.COMPLETED
                for d in step.depends_on if d in self.steps
            )
            if deps_met:
                result.append(step)
        return result

    def get_parallel_groups(self) -> Dict[str, List[RuntimeStep]]:
        runnable = self.get_runnable_steps()
        groups: Dict[str, List[RuntimeStep]] = {}
        for step in runnable:
            g = step.parallel_group or step.step_id
            groups.setdefault(g, []).append(step)
        return groups

    def has_pending_steps(self) -> bool:
        return any(s.status == RuntimeStepStatus.PENDING for s in self.steps.values())

    def is_terminal(self) -> bool:
        return self.status in (
            RuntimeWorkflowStatus.COMPLETED,
            RuntimeWorkflowStatus.FAILED,
            RuntimeWorkflowStatus.CANCELLED,
        )


class ExecutionPlanInput(BaseModel):
    plan_id: str
    goal: str
    steps: List[Dict[str, Any]]
    variables: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowSummary(BaseModel):
    workflow_id: str
    name: str
    status: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    created_at: datetime
    updated_at: datetime
    duration_ms: Optional[float] = None
