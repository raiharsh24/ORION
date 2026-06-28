"""
WorkflowEngine — central coordinator for all workflow executions.

Responsibilities:
  - CRUD for workflow definitions (in-memory store)
  - Start / Pause / Resume / Cancel / Restart / Retry operations
  - Spawning WorkflowRunner instances per active workflow
  - Exposing active workflow states for Kernel health checks
  - Streaming telemetry through EventBus

Registered in the Kernel as "workflow_engine".
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger

from app.workflow.workflow import Workflow, WorkflowNode, WorkflowNodeStatus, WorkflowStatus
from app.workflow.executor import WorkflowNodeExecutor
from app.workflow.runner import WorkflowRunner
from app.workflow.history import WorkflowHistory, WorkflowRunStatus


class WorkflowEngine:
    """
    Central coordinator for multi-step workflow execution.

    Integrations (injected via DI):
      - mission_engine      → MISSION nodes
      - desktop_automation  → DESKTOP_ACTION nodes
      - desktop_controller  → fallback desktop control
      - knowledge_engine    → KNOWLEDGE_QUERY nodes
      - planner             → PLANNER_STEP nodes
      - llm_router          → LLM_PROMPT nodes
      - event_bus           → lifecycle telemetry streaming
      - history             → WorkflowHistory persistence
    """

    def __init__(
        self,
        mission_engine: Optional[Any] = None,
        desktop_automation: Optional[Any] = None,
        desktop_controller: Optional[Any] = None,
        knowledge_engine: Optional[Any] = None,
        planner: Optional[Any] = None,
        llm_router: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        history: Optional[WorkflowHistory] = None,
    ) -> None:
        self._mission_engine     = mission_engine
        self._desktop_automation = desktop_automation
        self._desktop_controller = desktop_controller
        self._knowledge_engine   = knowledge_engine
        self._planner            = planner
        self._llm_router         = llm_router
        self._event_bus          = event_bus
        self._history            = history or WorkflowHistory()

        # Workflow store: workflow_id → Workflow
        self._workflows: Dict[str, Workflow] = {}
        # Active runners: workflow_id → WorkflowRunner
        self._runners: Dict[str, WorkflowRunner] = {}

    # -----------------------------------------------------------------------
    # Workflow CRUD
    # -----------------------------------------------------------------------

    def create_workflow(self, workflow: Workflow) -> Workflow:
        """
        Registers a new workflow definition.
        Assigns a new ID if none provided.
        """
        if not workflow.id:
            workflow.id = uuid.uuid4().hex
        workflow.created_at = datetime.now(timezone.utc)
        workflow.updated_at = datetime.now(timezone.utc)
        self._workflows[workflow.id] = workflow
        logger.info(f"[Engine] Workflow '{workflow.name}' registered (id={workflow.id})")
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Returns a workflow by ID."""
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[Workflow]:
        """Returns all registered workflows."""
        return list(self._workflows.values())

    def delete_workflow(self, workflow_id: str) -> bool:
        """Removes a workflow (only if not actively running)."""
        if workflow_id in self._runners:
            logger.warning(f"[Engine] Cannot delete running workflow '{workflow_id}'")
            return False
        removed = self._workflows.pop(workflow_id, None)
        return removed is not None

    # -----------------------------------------------------------------------
    # Execution lifecycle
    # -----------------------------------------------------------------------

    async def start(self, workflow_id: str) -> Optional[str]:
        """
        Starts workflow execution.

        Args:
            workflow_id: ID of a registered workflow.

        Returns:
            run_id of the new execution run, or None on error.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            logger.error(f"[Engine] Workflow '{workflow_id}' not found.")
            return None

        if workflow_id in self._runners:
            runner = self._runners[workflow_id]
            if not (runner._task and runner._task.done()):
                logger.warning(f"[Engine] Workflow '{workflow_id}' already running.")
                return None

        # Reset all node statuses
        for node in workflow.nodes.values():
            node.status = WorkflowNodeStatus.PENDING
            node.error = None
            node.outputs = {}
            node.started_at = None
            node.finished_at = None
            node.retry_count = 0
            node.loop_count = 0

        workflow.status = WorkflowStatus.RUNNING
        workflow.updated_at = datetime.now(timezone.utc)

        run = self._history.create_run(workflow_id, workflow.name)

        executor = self._build_executor()
        runner = WorkflowRunner(
            workflow=workflow,
            run=run,
            executor=executor,
            history=self._history,
            event_bus=self._event_bus,
        )
        self._runners[workflow_id] = runner
        runner.start()

        logger.info(
            f"[Engine] Started workflow '{workflow.name}' "
            f"(wf_id={workflow_id}, run_id={run.run_id})"
        )
        return run.run_id

    async def pause(self, workflow_id: str) -> bool:
        """Pauses a running workflow at the next safe checkpoint."""
        runner = self._runners.get(workflow_id)
        if not runner:
            logger.warning(f"[Engine] No active runner for workflow '{workflow_id}'")
            return False
        runner.pause()
        return True

    async def resume(self, workflow_id: str) -> bool:
        """Resumes a paused workflow."""
        runner = self._runners.get(workflow_id)
        if not runner:
            logger.warning(f"[Engine] No runner to resume for workflow '{workflow_id}'")
            return False
        runner.resume()
        return True

    async def cancel(self, workflow_id: str) -> bool:
        """Cancels an active workflow execution."""
        runner = self._runners.pop(workflow_id, None)
        if not runner:
            logger.warning(f"[Engine] No runner to cancel for workflow '{workflow_id}'")
            return False
        runner.cancel()
        logger.info(f"[Engine] Workflow '{workflow_id}' cancelled.")
        return True

    async def restart(self, workflow_id: str) -> Optional[str]:
        """
        Cancels the current run (if active) and starts a fresh one.

        Returns:
            New run_id on success, or None on error.
        """
        await self.cancel(workflow_id)
        return await self.start(workflow_id)

    async def retry_node(self, workflow_id: str, node_id: str) -> bool:
        """
        Resets a failed node to PENDING so it will be re-executed
        in the next runner loop tick.

        Args:
            workflow_id: Owning workflow.
            node_id:     The node to retry.

        Returns:
            True if the node was reset, False otherwise.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False
        node = workflow.nodes.get(node_id)
        if not node or node.status != WorkflowNodeStatus.FAILED:
            logger.warning(
                f"[Engine] Cannot retry node '{node_id}' — "
                f"status={node.status.value if node else 'not_found'}"
            )
            return False

        node.status = WorkflowNodeStatus.PENDING
        node.error = None
        node.retry_count = 0

        # If a runner exists and is paused/running, it will pick it up
        runner = self._runners.get(workflow_id)
        if not runner or (runner._task and runner._task.done()):
            # Re-start the runner to pick up the reset node
            await self.start(workflow_id)

        logger.info(f"[Engine] Node '{node_id}' in workflow '{workflow_id}' reset for retry.")
        return True

    # -----------------------------------------------------------------------
    # Observability
    # -----------------------------------------------------------------------

    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """
        Returns a summary of all currently running workflows.
        Used by Kernel health checks and streaming telemetry.
        """
        active = []
        for wf_id, runner in self._runners.items():
            if runner._task and not runner._task.done():
                wf = self._workflows.get(wf_id)
                run = runner._run
                active.append({
                    "workflow_id":          wf_id,
                    "workflow_name":        wf.name if wf else "unknown",
                    "run_id":               run.run_id,
                    "status":               run.status.value,
                    "current_node_id":      run.current_node_id,
                    "completed_nodes":      len(run.completed_nodes),
                    "failed_nodes":         len(run.failed_nodes),
                    "total_retries":        run.total_retries,
                    "duration_seconds":     round(run.elapsed_seconds(), 2),
                })
        return active

    def health(self) -> Dict[str, Any]:
        """
        Returns subsystem health info for the Kernel health check.
        Compatible with check_service_health() expectations.
        """
        active_count = sum(
            1 for runner in self._runners.values()
            if runner._task and not runner._task.done()
        )
        return {
            "status":             "HEALTHY",
            "active_workflows":   active_count,
            "total_workflows":    len(self._workflows),
            "total_runs":         len(self._history.list_runs(limit=9999)),
        }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_executor(self) -> WorkflowNodeExecutor:
        """Constructs a WorkflowNodeExecutor with current DI references."""
        return WorkflowNodeExecutor(
            mission_engine=self._mission_engine,
            desktop_automation=self._desktop_automation,
            desktop_controller=self._desktop_controller,
            knowledge_engine=self._knowledge_engine,
            planner=self._planner,
            llm_router=self._llm_router,
            event_bus=self._event_bus,
        )
