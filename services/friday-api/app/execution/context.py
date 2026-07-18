import time
import uuid
from typing import Dict, Any, Optional, Set, Callable, List
from dataclasses import dataclass, field
from enum import Enum


class Stage(Enum):
    INTENT = "intent"
    PLANNING = "planning"
    MEMORY = "memory"
    GOAL_PLANNING = "goal_planning"
    TOOL_SELECTION = "tool_selection"
    EXECUTION = "execution"
    REFLECTION = "reflection"
    ENRICHMENT = "enrichment"
    LLM = "llm"
    RESPONSE = "response"


class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise CancelledError("Execution cancelled")


class CancelledError(Exception):
    pass


@dataclass
class StageRecord:
    name: str
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    output: Any = None


@dataclass
class ExecutionContext:
    execution_id: str = ""
    session_id: Optional[str] = None
    prompt: str = ""
    provider_name: str = "gemini"

    intent: Any = None
    plan: Any = None
    goal_plan: Any = None
    memory_context: str = ""
    selected_tools: List[Any] = field(default_factory=list)
    tool_output: str = ""
    tool_used: Optional[str] = None
    enrichment_context: str = ""
    llm_response: str = ""
    final_response: Any = None
    reflection_report: Optional[Any] = None
    workspace_context: Optional[Any] = None

    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    stage_records: Dict[str, StageRecord] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    confirmed: bool = False
    confirmation_token: Optional[str] = None
    confirmation_required: bool = False

    def __post_init__(self) -> None:
        if not self.execution_id:
            self.execution_id = str(uuid.uuid4())
        for stage in Stage:
            self.stage_records[stage.value] = StageRecord(name=stage.value)

    def start_stage(self, stage: Stage) -> None:
        self.cancellation_token.check()
        record = self.stage_records[stage.value]
        record.status = StageStatus.RUNNING
        record.started_at = time.time()

    def complete_stage(self, stage: Stage, output: Any = None) -> None:
        record = self.stage_records[stage.value]
        record.status = StageStatus.COMPLETED
        record.completed_at = time.time()
        record.duration_ms = (record.completed_at - (record.started_at or record.completed_at)) * 1000
        record.output = output

    def fail_stage(self, stage: Stage, error: str) -> None:
        record = self.stage_records[stage.value]
        record.status = StageStatus.FAILED
        record.completed_at = time.time()
        record.duration_ms = (record.completed_at - (record.started_at or record.completed_at)) * 1000
        record.error = error
        self.errors.append(f"{stage.value}: {error}")

    def skip_stage(self, stage: Stage, reason: str = "") -> None:
        record = self.stage_records[stage.value]
        record.status = StageStatus.SKIPPED
        record.completed_at = time.time()
        record.error = reason

    def cancel(self) -> None:
        self.cancellation_token.cancel()

    @property
    def cancelled(self) -> bool:
        return self.cancellation_token.cancelled

    def elapsed_ms(self) -> float:
        total = sum(s.duration_ms for s in self.stage_records.values() if s.duration_ms > 0)
        return total
