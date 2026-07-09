from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExecutionEvent:
    topic: str = ""
    execution_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageStarted(ExecutionEvent):
    stage: str = ""

    def __post_init__(self) -> None:
        self.topic = f"Execution.StageStarted.{self.stage}"


@dataclass
class StageCompleted(ExecutionEvent):
    stage: str = ""
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        self.topic = f"Execution.StageCompleted.{self.stage}"


@dataclass
class StageFailed(ExecutionEvent):
    stage: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        self.topic = f"Execution.StageFailed.{self.stage}"


@dataclass
class ExecutionStarted(ExecutionEvent):
    def __post_init__(self) -> None:
        self.topic = "Execution.Started"


@dataclass
class ExecutionCompleted(ExecutionEvent):
    success: bool = True
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        self.topic = "Execution.Completed"


@dataclass
class ExecutionCancelled(ExecutionEvent):
    def __post_init__(self) -> None:
        self.topic = "Execution.Cancelled"


@dataclass
class ExecutionProgress(ExecutionEvent):
    stage: str = ""
    progress_pct: float = 0.0
    message: str = ""

    def __post_init__(self) -> None:
        self.topic = "Execution.Progress"
