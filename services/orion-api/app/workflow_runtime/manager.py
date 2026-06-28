import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from loguru import logger

from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeWorkflowStatus, RuntimeStep, RuntimeStepStatus,
    ExecutionPlanInput, RetryPolicy, WorkflowSummary
)
from app.workflow_runtime.events import (
    WorkflowStarted, WorkflowPaused, WorkflowResumed,
    WorkflowCompleted, WorkflowFailed, WorkflowCancelled,
)
from app.workflow_runtime.persistence import WorkflowPersistence
from app.workflow_runtime.executor import WorkflowRuntimeExecutor
from app.workflow_runtime.checkpoints import CheckpointManager


class WorkflowRuntimeManager:
    def __init__(
        self,
        persistence: WorkflowPersistence,
        executor: WorkflowRuntimeExecutor,
        event_bus: Any = None,
    ) -> None:
        self._persistence = persistence
        self._executor = executor
        self._event_bus = event_bus
        self._active_runs: Dict[str, asyncio.Task] = {}
        self._active_workflows: Dict[str, RuntimeWorkflow] = {}
        self._start_times: Dict[str, float] = {}

    async def start_from_plan(self, plan: ExecutionPlanInput) -> RuntimeWorkflow:
        workflow = self._executor.build_from_plan(plan)
        workflow.status = RuntimeWorkflowStatus.PENDING
        await self._persistence.save(workflow)
        return await self._start_execution(workflow)

    async def start_from_workflow(self, workflow: RuntimeWorkflow) -> RuntimeWorkflow:
        workflow.status = RuntimeWorkflowStatus.PENDING
        await self._persistence.save(workflow)
        return await self._start_execution(workflow)

    async def _start_execution(self, workflow: RuntimeWorkflow) -> RuntimeWorkflow:
        workflow_id = workflow.workflow_id
        existing = self._active_runs.get(workflow_id)
        if existing is not None and not existing.done():
            logger.warning(f"Workflow '{workflow_id}' is already running, skipping duplicate start")
            return workflow
        self._active_workflows[workflow_id] = workflow
        self._start_times[workflow_id] = time.time()

        task = asyncio.create_task(self._run_workflow(workflow_id))
        self._active_runs[workflow_id] = task

        self._event_bus and self._event_bus.publish_background(WorkflowStarted(
            workflow_id, workflow.name, len(workflow.steps)
        ))
        logger.info(f"Workflow '{workflow.name}' ({workflow_id}) started with {len(workflow.steps)} steps")
        return workflow

    async def _run_workflow(self, workflow_id: str) -> None:
        workflow = self._active_workflows.get(workflow_id)
        if not workflow:
            return

        try:
            workflow.status = RuntimeWorkflowStatus.RUNNING
            workflow.started_at = datetime.now(timezone.utc)
            await self._persistence.save(workflow)

            while workflow.has_pending_steps() and not workflow.is_terminal():
                groups = workflow.get_parallel_groups()
                if not groups:
                    break

                for group_id, steps in groups.items():
                    if len(steps) == 1:
                        step = steps[0]
                        try:
                            await self._executor.execute_step(
                                workflow, step, workflow.variables
                            )
                            await self._persistence.save(workflow)
                        except Exception:
                            if step.retry_count < step.retry_policy.max_retries:
                                step.retry_count += 1
                                step.status = RuntimeStepStatus.PENDING
                                logger.info(f"Will retry step '{step.name}' (attempt {step.retry_count})")
                                await self._persistence.save(workflow)
                            else:
                                failed = self._check_failure_propagation(workflow)
                                await self._persistence.save(workflow)
                                if failed:
                                    return
                    else:
                        try:
                            await self._executor.execute_parallel_steps(
                                workflow, steps, workflow.variables
                            )
                            await self._persistence.save(workflow)
                        except Exception as e:
                            logger.error(f"Parallel group {group_id} failed: {e}")

                workflow = self._active_workflows.get(workflow_id)
                if not workflow or workflow.is_terminal():
                    return

            await self._finalize_workflow(workflow)

        except asyncio.CancelledError:
            logger.info(f"Workflow '{workflow_id}' execution cancelled")
            workflow.status = RuntimeWorkflowStatus.CANCELLED
            await self._persistence.save(workflow)
            self._event_bus and self._event_bus.publish_background(WorkflowCancelled(workflow_id))
        except Exception as e:
            error = str(e)
            logger.error(f"Workflow '{workflow_id}' runtime error: {error}")
            workflow.status = RuntimeWorkflowStatus.FAILED
            workflow.error = error
            await self._persistence.save(workflow)
            self._event_bus and self._event_bus.publish_background(WorkflowFailed(workflow_id, error))
        finally:
            self._active_runs.pop(workflow_id, None)
            self._start_times.pop(workflow_id, None)

    async def _finalize_workflow(self, workflow: RuntimeWorkflow) -> None:
        failed = [
            s for s in workflow.steps.values()
            if s.status == RuntimeStepStatus.FAILED
        ]
        if failed:
            workflow.status = RuntimeWorkflowStatus.FAILED
            workflow.error = f"{len(failed)} step(s) failed"
            self._event_bus and self._event_bus.publish_background(WorkflowFailed(workflow.workflow_id, workflow.error))
        else:
            workflow.status = RuntimeWorkflowStatus.COMPLETED
            self._event_bus and self._event_bus.publish_background(WorkflowCompleted(
                workflow.workflow_id,
                len(workflow.steps),
                len(failed)
            ))
        workflow.completed_at = datetime.now(timezone.utc)
        await self._persistence.save(workflow)
        if self._executor._checkpoints:
            await self._executor._checkpoints.clear_workflow_checkpoints(workflow.workflow_id)
        logger.info(f"Workflow '{workflow.name}' finalized: {workflow.status.value}")

    def _check_failure_propagation(self, workflow: RuntimeWorkflow) -> bool:
        failed_steps = [
            s for s in workflow.steps.values()
            if s.status == RuntimeStepStatus.FAILED
        ]
        all_failed_recoverable = all(
            s.retry_count < s.retry_policy.max_retries
            for s in failed_steps
        )
        if not all_failed_recoverable and failed_steps:
            workflow.status = RuntimeWorkflowStatus.FAILED
            workflow.error = f"Step(s) failed after max retries: {', '.join(s.name for s in failed_steps)}"
            self._event_bus and self._event_bus.publish_background(WorkflowFailed(workflow.workflow_id, workflow.error))
            return True
        return False

    async def pause(self, workflow_id: str) -> bool:
        workflow = self._active_workflows.get(workflow_id)
        if not workflow or workflow.status != RuntimeWorkflowStatus.RUNNING:
            return False
        workflow.status = RuntimeWorkflowStatus.PAUSED
        await self._persistence.save(workflow)
        self._event_bus and self._event_bus.publish_background(WorkflowPaused(workflow_id))
        logger.info(f"Workflow '{workflow_id}' paused")
        return True

    async def resume(self, workflow_id: str) -> bool:
        workflow = self._active_workflows.get(workflow_id)
        if not workflow or workflow.status != RuntimeWorkflowStatus.PAUSED:
            stored = await self._persistence.load(workflow_id)
            if stored and stored.status == RuntimeWorkflowStatus.PAUSED:
                self._active_workflows[workflow_id] = stored
                workflow = stored
            else:
                return False

        workflow.status = RuntimeWorkflowStatus.RUNNING
        await self._persistence.save(workflow)
        self._event_bus and self._event_bus.publish_background(WorkflowResumed(workflow_id))
        logger.info(f"Workflow '{workflow_id}' resumed")

        if workflow_id not in self._active_runs or self._active_runs[workflow_id].done():
            task = asyncio.create_task(self._run_workflow(workflow_id))
            self._active_runs[workflow_id] = task
        return True

    async def cancel(self, workflow_id: str) -> bool:
        task = self._active_runs.pop(workflow_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        workflow = self._active_workflows.pop(workflow_id, None)
        if not workflow:
            workflow = await self._persistence.load(workflow_id)
        if workflow:
            workflow.status = RuntimeWorkflowStatus.CANCELLED
            await self._persistence.save(workflow)
            self._event_bus and self._event_bus.publish_background(WorkflowCancelled(workflow_id))
            logger.info(f"Workflow '{workflow_id}' cancelled")
            return True
        return False

    async def retry_step(self, workflow_id: str, step_id: str) -> bool:
        workflow = self._active_workflows.get(workflow_id)
        if not workflow:
            stored = await self._persistence.load(workflow_id)
            if not stored:
                return False
            workflow = stored
            self._active_workflows[workflow_id] = workflow

        step = workflow.steps.get(step_id)
        if not step or step.status != RuntimeStepStatus.FAILED:
            return False

        step.status = RuntimeStepStatus.PENDING
        step.error = None
        step.result = None
        step.completed_at = None
        logger.info(f"Step '{step.name}' marked for retry")

        if workflow.status in (
            RuntimeWorkflowStatus.FAILED, RuntimeWorkflowStatus.CANCELLED
        ):
            workflow.status = RuntimeWorkflowStatus.RUNNING
            workflow.error = None
            if workflow_id not in self._active_runs or self._active_runs[workflow_id].done():
                task = asyncio.create_task(self._run_workflow(workflow_id))
                self._active_runs[workflow_id] = task

        await self._persistence.save(workflow)
        return True

    def get(self, workflow_id: str) -> Optional[RuntimeWorkflow]:
        return self._active_workflows.get(workflow_id)

    async def get_stored(self, workflow_id: str) -> Optional[RuntimeWorkflow]:
        wf = self._active_workflows.get(workflow_id)
        if wf:
            return wf
        return await self._persistence.load(workflow_id)

    def list_active(self) -> List[RuntimeWorkflow]:
        return list(self._active_workflows.values())

    async def list_all(self) -> List[RuntimeWorkflow]:
        return await self._persistence.list()

    async def list_summaries(self) -> List[WorkflowSummary]:
        workflows = await self._persistence.list()
        summaries = []
        for wf in workflows:
            total = len(wf.steps)
            completed = len([s for s in wf.steps.values()
                            if s.status == RuntimeStepStatus.COMPLETED])
            failed = len([s for s in wf.steps.values()
                          if s.status == RuntimeStepStatus.FAILED])
            duration = None
            if wf.started_at and wf.completed_at:
                duration = (wf.completed_at - wf.started_at).total_seconds() * 1000
            summaries.append(WorkflowSummary(
                workflow_id=wf.workflow_id,
                name=wf.name,
                status=wf.status.value,
                total_steps=total,
                completed_steps=completed,
                failed_steps=failed,
                created_at=wf.created_at,
                updated_at=wf.updated_at,
                duration_ms=duration
            ))
        return summaries

    async def recover(self) -> int:
        incomplete = await self._persistence.recover_incomplete()
        for wf in incomplete:
            self._active_workflows[wf.workflow_id] = wf
        logger.info(f"Recovered {len(incomplete)} incomplete workflows")
        return len(incomplete)

    def health(self) -> Dict:
        return {
            "status": "HEALTHY",
            "message": "WorkflowRuntimeManager operational.",
            "details": {
                "active_runs": len(self._active_runs),
                "active_workflows": len(self._active_workflows),
                "stored_count": self._persistence.count()
            }
        }


