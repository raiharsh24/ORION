from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEPENDENCY_AWARE = "dependency_aware"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ExecutionContext:
    tool_id: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 0
    retry_delay: float = 1.0
    priority: int = 0


@dataclass
class ExecutedTool:
    tool_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    retries: int = 0
    timeout_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    @property
    def runtime_ms(self) -> float:
        return self.duration_ms


@dataclass
class ExecutionReport:
    total_tools: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    timed_out: int = 0
    skipped: int = 0
    total_duration_ms: float = 0.0
    parallel_efficiency: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class ToolExecutionResult:
    execution_id: str = ""
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    results: List[ExecutedTool] = field(default_factory=list)
    report: ExecutionReport = field(default_factory=ExecutionReport)
    status: ExecutionStatus = ExecutionStatus.PENDING

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def tool_ids(self) -> List[str]:
        return [r.tool_id for r in self.results]
