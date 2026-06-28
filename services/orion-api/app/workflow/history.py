"""
Workflow execution history — persists workflow run records including telemetry,
node completion tracking, branch decisions, and retry counts.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from loguru import logger


class WorkflowRunStatus(str, Enum):
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    PAUSED    = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    CANCELLED = "CANCELLED"


class BranchDecision(BaseModel):
    """Records a conditional branch taken during execution."""
    node_id: str
    condition_result: bool
    branch_taken: str           # 'on_success' | 'on_failure'
    next_node_id: Optional[str]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkflowRun(BaseModel):
    """
    Complete execution record for a single workflow run.
    Tracks node-level outcomes, branch decisions, retries, and timing.
    """
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    workflow_id: str
    workflow_name: str
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING

    # Timing
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Execution tracking
    current_node_id: Optional[str] = None
    completed_nodes: List[str] = Field(default_factory=list)
    failed_nodes: List[str] = Field(default_factory=list)
    skipped_nodes: List[str] = Field(default_factory=list)

    # Telemetry
    retry_counts: Dict[str, int] = Field(default_factory=dict)   # node_id → retry count
    branch_decisions: List[BranchDecision] = Field(default_factory=list)
    variables_snapshot: Dict[str, Any] = Field(default_factory=dict)

    total_retries: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def elapsed_seconds(self) -> float:
        """Returns elapsed time from start until now (or finished_at)."""
        if not self.started_at:
            return 0.0
        end = self.finished_at or datetime.now(timezone.utc)
        start = self.started_at.replace(tzinfo=timezone.utc) if self.started_at.tzinfo is None else self.started_at
        end = end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end
        return (end - start).total_seconds()

    def to_telemetry_dict(self) -> Dict[str, Any]:
        """Compact dict suitable for streaming telemetry payloads."""
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "current_node_id": self.current_node_id,
            "completed_nodes": len(self.completed_nodes),
            "failed_nodes": len(self.failed_nodes),
            "total_retries": self.total_retries,
            "duration_seconds": round(self.elapsed_seconds(), 2),
            "branch_decisions": [
                {"node_id": bd.node_id, "branch": bd.branch_taken, "next": bd.next_node_id}
                for bd in self.branch_decisions[-3:]   # last 3 decisions
            ]
        }


class WorkflowHistory:
    """
    In-memory workflow execution history store.
    Persists WorkflowRun records keyed by run_id and workflow_id.
    """

    def __init__(self) -> None:
        self._runs: Dict[str, WorkflowRun] = {}          # run_id → WorkflowRun
        self._by_workflow: Dict[str, List[str]] = {}     # workflow_id → [run_id, ...]

    def create_run(self, workflow_id: str, workflow_name: str) -> WorkflowRun:
        """Creates and persists a new WorkflowRun record."""
        run = WorkflowRun(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=WorkflowRunStatus.PENDING,
            started_at=datetime.now(timezone.utc)
        )
        self._runs[run.run_id] = run
        self._by_workflow.setdefault(workflow_id, []).append(run.run_id)
        logger.info(f"[WorkflowHistory] Created run {run.run_id} for workflow '{workflow_name}'")
        return run

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Retrieves a run by its run_id."""
        return self._runs.get(run_id)

    def save_run(self, run: WorkflowRun) -> None:
        """Persists (upserts) a WorkflowRun."""
        self._runs[run.run_id] = run

    def list_runs(self, limit: int = 50) -> List[WorkflowRun]:
        """Returns recent runs (most-recent first)."""
        runs = list(self._runs.values())
        runs.sort(key=lambda r: r.started_at or datetime.min, reverse=True)
        return runs[:limit]

    def list_by_workflow(self, workflow_id: str) -> List[WorkflowRun]:
        """Returns all runs for a given workflow_id (most-recent first)."""
        run_ids = self._by_workflow.get(workflow_id, [])
        runs = [self._runs[rid] for rid in run_ids if rid in self._runs]
        runs.sort(key=lambda r: r.started_at or datetime.min, reverse=True)
        return runs

    def get_active_run(self, workflow_id: str) -> Optional[WorkflowRun]:
        """Returns the most recent RUNNING or PAUSED run for a workflow."""
        for run in self.list_by_workflow(workflow_id):
            if run.status in (WorkflowRunStatus.RUNNING, WorkflowRunStatus.PAUSED):
                return run
        return None

    def mark_node_completed(self, run: WorkflowRun, node_id: str) -> None:
        """Records a node as completed in the run."""
        if node_id not in run.completed_nodes:
            run.completed_nodes.append(node_id)
        run.current_node_id = None
        self.save_run(run)

    def mark_node_failed(self, run: WorkflowRun, node_id: str, error: str) -> None:
        """Records a node as failed in the run."""
        if node_id not in run.failed_nodes:
            run.failed_nodes.append(node_id)
        run.current_node_id = None
        run.error = error
        self.save_run(run)

    def record_branch(
        self,
        run: WorkflowRun,
        node_id: str,
        condition_result: bool,
        branch_taken: str,
        next_node_id: Optional[str]
    ) -> None:
        """Records a conditional branch decision."""
        decision = BranchDecision(
            node_id=node_id,
            condition_result=condition_result,
            branch_taken=branch_taken,
            next_node_id=next_node_id
        )
        run.branch_decisions.append(decision)
        self.save_run(run)

    def finish_run(self, run: WorkflowRun, status: WorkflowRunStatus, error: Optional[str] = None) -> None:
        """Marks a run as terminal and records duration."""
        run.status = status
        run.finished_at = datetime.now(timezone.utc)
        run.duration_seconds = run.elapsed_seconds()
        if error:
            run.error = error
        self.save_run(run)
        logger.info(
            f"[WorkflowHistory] Run {run.run_id} finished: {status.value} "
            f"in {run.duration_seconds:.2f}s"
        )
