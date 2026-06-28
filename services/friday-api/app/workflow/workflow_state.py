from enum import Enum
from typing import Dict, Any, Optional

class WorkflowStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class WorkflowState:
    """
    Tracks runtime variables and step execution contexts.

    TODO:
    - Persist variables between step triggers
    - Record active step indices
    - Store exceptions and failure context logs
    """
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.status: WorkflowStatus = WorkflowStatus.IDLE
        self.current_step_index: int = 0
        self.variables: Dict[str, Any] = {}
        self.error: Optional[str] = None
