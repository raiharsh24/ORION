from typing import Dict, Any, Optional, List
from loguru import logger

from app.workflow_runtime.models import (
    RuntimeWorkflow, ExecutionPlanInput, RuntimeWorkflowStatus
)
from app.workflow_runtime.manager import WorkflowRuntimeManager


class RuntimeSchedulerBridge:
    def __init__(
        self,
        workflow_manager: WorkflowRuntimeManager,
        agent_scheduler: Any = None,
    ) -> None:
        self._manager = workflow_manager
        self._agent_scheduler = agent_scheduler

    async def submit_plan(self, plan: ExecutionPlanInput) -> str:
        logger.info(f"Submitting plan '{plan.plan_id}' to workflow runtime")
        workflow = await self._manager.start_from_plan(plan)
        return workflow.workflow_id

    async def submit_workflow(self, workflow: RuntimeWorkflow) -> str:
        logger.info(f"Submitting workflow '{workflow.name}' to runtime")
        wf = await self._manager.start_from_workflow(workflow)
        return wf.workflow_id

    async def submit_and_wait(self, plan: ExecutionPlanInput) -> RuntimeWorkflow:
        logger.info(f"Submitting plan '{plan.plan_id}' and awaiting completion")
        workflow = await self._manager.start_from_plan(plan)
        task = self._manager._active_runs.get(workflow.workflow_id)
        if task:
            try:
                await task
            except Exception:
                pass
        completed = self._manager.get(workflow.workflow_id)
        if not completed:
            completed = await self._manager.get_stored(workflow.workflow_id)
        return completed or workflow

    async def schedule_plan(
        self,
        plan: ExecutionPlanInput,
        trigger: str = "immediate",
        cron_expr: Optional[str] = None,
    ) -> str:
        workflow = self._manager._executor.build_from_plan(plan)

        if trigger == "immediate":
            workflow.status = RuntimeWorkflowStatus.PENDING
            wf = await self._manager.start_from_workflow(workflow)
            return wf.workflow_id

        elif trigger == "cron" and cron_expr and self._agent_scheduler:
            from app.agents.models import AgentTask
            schedule_task = AgentTask(
                task_id=f"sched-{workflow.workflow_id}",
                type="system",
                payload={
                    "action": "start_workflow",
                    "workflow_id": workflow.workflow_id,
                    "plan": plan.model_dump(),
                },
                cron_expr=cron_expr,
            )
            await self._agent_scheduler.schedule(schedule_task)
            logger.info(f"Workflow '{workflow.workflow_id}' scheduled with cron '{cron_expr}'")
            return workflow.workflow_id

        else:
            raise ValueError(f"Unsupported trigger '{trigger}' or missing scheduler")

    async def cancel(self, workflow_id: str) -> bool:
        return await self._manager.cancel(workflow_id)

    async def pause(self, workflow_id: str) -> bool:
        return await self._manager.pause(workflow_id)

    async def resume(self, workflow_id: str) -> bool:
        return await self._manager.resume(workflow_id)

    async def retry_step(self, workflow_id: str, step_id: str) -> bool:
        return await self._manager.retry_step(workflow_id, step_id)

    def get(self, workflow_id: str) -> Optional[RuntimeWorkflow]:
        return self._manager.get(workflow_id)

    async def get_stored(self, workflow_id: str) -> Optional[RuntimeWorkflow]:
        return await self._manager.get_stored(workflow_id)

    def list_active(self) -> List[RuntimeWorkflow]:
        return self._manager.list_active()

    async def list_all(self) -> List[RuntimeWorkflow]:
        return await self._manager.list_all()

    async def list_summaries(self) -> List[Dict[str, Any]]:
        summaries = await self._manager.list_summaries()
        return [s.model_dump() for s in summaries]

    async def recover(self) -> int:
        return await self._manager.recover()

    def health(self) -> Dict:
        return {
            "status": "HEALTHY",
            "message": "RuntimeSchedulerBridge operational.",
            "active_workflows": len(self._manager.list_active()),
        }
