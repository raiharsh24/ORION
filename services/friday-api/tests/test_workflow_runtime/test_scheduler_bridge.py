import pytest
import tempfile
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any

from app.workflow_runtime.scheduler_bridge import RuntimeSchedulerBridge
from app.workflow_runtime.manager import WorkflowRuntimeManager
from app.workflow_runtime.executor import WorkflowRuntimeExecutor
from app.workflow_runtime.persistence import WorkflowPersistence
from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RuntimeStepStatus, RuntimeWorkflowStatus,
    ExecutionPlanInput, RetryPolicy
)
from app.agents.models import AgentTask


def _make_coordinator():
    c = MagicMock()
    c.delegate = AsyncMock(return_value={"output": "ok"})
    return c


@pytest.mark.anyio
async def test_submit_plan():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(agent_coordinator=_make_coordinator())
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        plan = ExecutionPlanInput(
            plan_id="plan-1",
            goal="Test",
            steps=[{"step_id": "s1", "name": "S1", "type": "tool", "input": {}}],
        )
        wf_id = await bridge.submit_plan(plan)
        assert wf_id == "plan-plan-1"
        import asyncio
        await asyncio.sleep(0.1)
        assert len(bridge.list_active()) == 1


@pytest.mark.anyio
async def test_submit_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(agent_coordinator=_make_coordinator())
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
        wf.steps["s1"] = RuntimeStep(
            step_id="s1", name="S1", step_type="tool",
            input={}, retry_policy=RetryPolicy()
        )
        wf_id = await bridge.submit_workflow(wf)
        assert wf_id == "wf-1"


@pytest.mark.anyio
async def test_cancel_pause_resume_retry():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        coordinator = MagicMock()
        async def slow_delegate(task):
            import asyncio
            await asyncio.sleep(10)
            return {"output": "ok"}
        coordinator.delegate = slow_delegate
        executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
        s1 = RuntimeStep(step_id="s1", name="S1", step_type="tool",
                         input={}, retry_policy=RetryPolicy())
        wf.steps["s1"] = s1

        await bridge.submit_workflow(wf)
        import asyncio
        await asyncio.sleep(0.1)

        paused = await bridge.pause("wf-1")
        assert paused is True

        resumed = await bridge.resume("wf-1")
        assert resumed is True

        s1.status = RuntimeStepStatus.FAILED
        s1.error = "fail"
        retried = await bridge.retry_step("wf-1", "s1")
        assert retried is True
        assert s1.status == RuntimeStepStatus.PENDING


@pytest.mark.anyio
async def test_get_and_list():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(agent_coordinator=_make_coordinator())
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
        wf.steps["s1"] = RuntimeStep(
            step_id="s1", name="S1", step_type="tool",
            input={}, retry_policy=RetryPolicy()
        )
        await bridge.submit_workflow(wf)
        import asyncio
        await asyncio.sleep(0.1)

        found = bridge.get("wf-1")
        assert found is not None

        stored = await bridge.get_stored("wf-1")
        assert stored is not None

        all_wf = await bridge.list_all()
        assert len(all_wf) >= 1

        summaries = await bridge.list_summaries()
        assert len(summaries) >= 1


@pytest.mark.anyio
async def test_schedule_plan_immediate():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(agent_coordinator=_make_coordinator())
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        plan = ExecutionPlanInput(
            plan_id="plan-1",
            goal="Test",
            steps=[{"step_id": "s1", "name": "S1", "type": "tool", "input": {}}],
        )
        wf_id = await bridge.schedule_plan(plan, trigger="immediate")
        assert wf_id is not None


@pytest.mark.anyio
async def test_schedule_plan_cron():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(agent_coordinator=_make_coordinator())
        scheduler = MagicMock()
        scheduler.schedule = AsyncMock()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager, agent_scheduler=scheduler)

        plan = ExecutionPlanInput(
            plan_id="plan-1",
            goal="Test",
            steps=[{"step_id": "s1", "name": "S1", "type": "tool", "input": {}}],
        )
        wf_id = await bridge.schedule_plan(plan, trigger="cron", cron_expr="*/5 * * * *")
        assert wf_id is not None
        scheduler.schedule.assert_awaited_once()


@pytest.mark.anyio
async def test_recover():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(agent_coordinator=_make_coordinator())
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        running = RuntimeWorkflow(workflow_id="wf-run", name="Running")
        running.status = RuntimeWorkflowStatus.RUNNING  # noqa: F821
        await persistence.save(running)

        recovered = await bridge.recover()
        assert recovered == 1


def test_health():
    bridge = RuntimeSchedulerBridge(
        workflow_manager=MagicMock(),
    )
    bridge._manager.list_active = MagicMock(return_value=["wf-1"])
    health = bridge.health()
    assert health["status"] == "HEALTHY"
