import uuid
import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RuntimeStepStatus, ExecutionPlanInput, RetryPolicy
)
from app.workflow_runtime.events import (
    WorkflowStepStarted, WorkflowStepCompleted
)
from app.workflow_runtime.checkpoints import CheckpointManager
from app.agents.models import AgentTask


class WorkflowRuntimeExecutor:
    def __init__(
        self,
        agent_coordinator: Any = None,
        shared_context: Any = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        event_bus: Any = None,
    ) -> None:
        self._coordinator = agent_coordinator
        self._shared_context = shared_context
        self._checkpoints = checkpoint_manager
        self._event_bus = event_bus

    async def execute_step(
        self,
        workflow: RuntimeWorkflow,
        step: RuntimeStep,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info(f"Executing step '{step.name}' ({step.step_id}) type={step.step_type}")

        step.status = RuntimeStepStatus.RUNNING
        step.started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        self._publish_event(WorkflowStepStarted(
            workflow.workflow_id, step.step_id, step.name, step.step_type
        ))

        try:
            resolved_inputs = self._resolve_variables(step.input, variables)

            worker_task = AgentTask(
                task_id=f"wf-{workflow.workflow_id}-{step.step_id}",
                type=step.step_type,
                payload={
                    "step_type": step.step_type,
                    "inputs": resolved_inputs,
                    "workflow_id": workflow.workflow_id,
                    "step_id": step.step_id,
                },
                timeout=step.timeout,
                max_retries=step.retry_policy.max_retries,
            )

            start = time.time()
            result = await self._coordinator.delegate(worker_task)
            duration_ms = (time.time() - start) * 1000

            step.status = RuntimeStepStatus.COMPLETED
            step.result = result
            step.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

            if result:
                variables.update({f"{step.step_id}.output": result})

            if self._checkpoints:
                await self._checkpoints.save_checkpoint(
                    workflow.workflow_id, step.step_id,
                    {"result": result, "status": "COMPLETED", "duration_ms": duration_ms}
                )

            self._publish_event(WorkflowStepCompleted(
                workflow.workflow_id, step.step_id, success=True
            ))
            logger.info(f"Step '{step.name}' completed in {duration_ms:.1f}ms")
            return result

        except Exception as e:
            error_msg = str(e)
            step.status = RuntimeStepStatus.FAILED
            step.error = error_msg
            step.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            self._publish_event(WorkflowStepCompleted(
                workflow.workflow_id, step.step_id, success=False
            ))
            logger.error(f"Step '{step.name}' failed: {error_msg}")
            raise

    async def execute_parallel_steps(
        self,
        workflow: RuntimeWorkflow,
        steps: List[RuntimeStep],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        import asyncio
        coros = [self.execute_step(workflow, s, variables) for s in steps]
        results = await asyncio.gather(*coros, return_exceptions=True)

        merged: Dict[str, Any] = {}
        for step, result in zip(steps, results):
            if isinstance(result, Exception):
                merged[step.step_id] = {"error": str(result)}
            else:
                merged[step.step_id] = result
        return merged

    def build_from_plan(self, plan: ExecutionPlanInput) -> RuntimeWorkflow:
        workflow_id = f"plan-{plan.plan_id}"
        steps: Dict[str, RuntimeStep] = {}

        for i, step_data in enumerate(plan.steps):
            step_id = step_data.get("step_id", f"step_{i}")
            steps[step_id] = RuntimeStep(
                step_id=step_id,
                name=step_data.get("name", f"Step {i}"),
                step_type=step_data.get("type", "tool"),
                input=step_data.get("input", {}),
                depends_on=step_data.get("depends_on", []),
                timeout=step_data.get("timeout"),
                retry_policy=RetryPolicy(**step_data.get("retry_policy", {})),
                parallel_group=step_data.get("parallel_group"),
            )

        return RuntimeWorkflow(
            workflow_id=workflow_id,
            name=plan.goal[:80] if plan.goal else f"Plan {plan.plan_id}",
            steps=steps,
            variables=dict(plan.variables),
            source_plan=plan.model_dump(),
            metadata=plan.metadata,
        )

    def _resolve_variables(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in template.items():
            if isinstance(value, str) and "{{" in value:
                resolved = value
                for var_key, var_val in variables.items():
                    placeholder = "{{" + var_key + "}}"
                    resolved = resolved.replace(placeholder, str(var_val))
                for step_id, step_var in variables.items():
                    if isinstance(step_var, dict):
                        for k, v in step_var.items():
                            placeholder = "{{" + step_id + "." + k + "}}"
                            resolved = resolved.replace(placeholder, str(v))
                result[key] = resolved
            elif isinstance(value, dict):
                result[key] = self._resolve_variables(value, variables)
            elif isinstance(value, list):
                result[key] = [
                    self._resolve_variables(v, variables) if isinstance(v, dict)
                    else self._resolve_variables({"_": v}, variables).get("_", v)
                    if isinstance(v, str) and "{{" in v else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def _publish_event(self, event: Any) -> None:
        if not self._event_bus:
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._event_bus.publish(event))
        except RuntimeError:
            asyncio.run(self._event_bus.publish(event))
        except Exception as e:
            logger.error(f"Executor event publish failed: {e}")

    def health(self) -> Dict:
        return {"status": "HEALTHY", "message": "WorkflowRuntimeExecutor operational."}
