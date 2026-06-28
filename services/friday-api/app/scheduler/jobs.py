from typing import Dict, Any, Optional
from app.scheduler.triggers import JobTrigger

class ScheduledJob:
    """
    Represents a registered, timed automation execution task.

    TODO:
    - Map job IDs to specific workflow blueprint triggers
    - Keep track of argument kwargs lists
    - Monitor execution metrics (such as last run details and exceptions)
    """
    def __init__(
        self,
        job_id: str,
        workflow_id: str,
        trigger: JobTrigger,
        args: Optional[Dict[str, Any]] = None
    ) -> None:
        self.job_id = job_id
        self.workflow_id = workflow_id
        self.trigger = trigger
        self.args = args or {}
        self.last_run_timestamp: Optional[float] = None
        self.success_count: int = 0
