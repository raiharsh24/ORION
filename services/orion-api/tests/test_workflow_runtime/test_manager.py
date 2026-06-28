import pytest
import tempfile
import uuid
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any

from app.workflow_runtime.manager import WorkflowRuntimeManager
from app.workflow_runtime.executor import WorkflowRuntimeExecutor
from app.workflow_runtime.persistence import WorkflowPersistence
from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RuntimeStepStatus,
    RuntimeWorkflowStatus, ExecutionPlanInput, RetryPolicy
)
from app.agents.models import AgentTask


def _make_coordinator():
    c = MagicMock()
    c.delegate = AsyncMock(return_value={"output": "ok"})
    return c


def _make_persistence(tmp):
    return WorkflowPersistence(persist_dir=tmp)


def _make_executor(coordinator=None, cp=None):
    return WorkflowRuntimeExecutor(
        agent_coordinator=coordinator or _make_coordinator(),
        checkpoint_manager=cp,
    )


def _make_workflow(**overrides) -> RuntimeWorkflow:
    wf = RuntimeWorkflow(
        workflow_id=overrides.get("workflow_id", "wf-1"),
        name=overrides.get("name", "Test"),
    )
    s1 = RuntimeStep(
        step_id="s1", name="Step 1", step_type="tool",
        input={"cmd": "echo hi"}, retry_policy=RetryPolicy(max_retries=0),
    )
    wf.steps = {"s1": s1}
    return wf


@pytest.mark.anyio
async def test_start_workflow():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        executor = _make_executor()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        wf = _make_workflow()
        result = await manager.start_from_workflow(wf)
        assert result.status == RuntimeWorkflowStatus.PENDING
        assert result.workflow_id == "wf-1"

        import asyncio
        await asyncio.sleep(0.1)

        active = manager.list_active()
        assert len(active) == 1


@pytest.mark.anyio
async def test_start_from_plan():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        executor = _make_executor()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        plan = ExecutionPlanInput(
            plan_id="plan-1",
            goal="Test plan",
            steps=[{"step_id": "s1", "name": "S1", "type": "tool", "input": {"cmd": "build"}}],
            variables={"env": "test"},
        )
        result = await manager.start_from_plan(plan)
        assert result.workflow_id == "plan-plan-1"

        import asyncio
        await asyncio.sleep(0.1)
        assert len(manager.list_active()) == 1


@pytest.mark.anyio
async def test_pause_resume():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        coordinator = MagicMock()
        async def slow_delegate(task):
            import asyncio
            await asyncio.sleep(10)
            return {"output": "ok"}
        coordinator.delegate = slow_delegate
        executor = _make_executor(coordinator=coordinator)
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        wf = _make_workflow()
        await manager.start_from_workflow(wf)

        import asyncio
        await asyncio.sleep(0.1)

        paused = await manager.pause("wf-1")
        assert paused is True
        stored = await manager.get_stored("wf-1")
        assert stored.status == RuntimeWorkflowStatus.PAUSED

        resumed = await manager.resume("wf-1")
        assert resumed is True


@pytest.mark.anyio
async def test_cancel():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        wf = _make_workflow()

        # Use a slow coordinator so we can cancel mid-flight
        coordinator = MagicMock()
        async def slow_delegate(task):
            import asyncio
            await asyncio.sleep(10)
            return {"output": "ok"}
        coordinator.delegate = slow_delegate

        executor = _make_executor(coordinator=coordinator)
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        await manager.start_from_workflow(wf)
        import asyncio
        await asyncio.sleep(0.05)

        cancelled = await manager.cancel("wf-1")
        assert cancelled is True

        stored = await manager.get_stored("wf-1")
        assert stored.status == RuntimeWorkflowStatus.CANCELLED


@pytest.mark.anyio
async def test_retry_step():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        coordinator = MagicMock()
        coordinator.delegate = AsyncMock(side_effect=RuntimeError("fail"))
        executor = _make_executor(coordinator=coordinator)
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        wf = _make_workflow()
        await manager.start_from_workflow(wf)
        import asyncio
        await asyncio.sleep(0.1)

        retried = await manager.retry_step("wf-1", "s1")
        assert retried is True

        step = wf.steps["s1"]
        assert step.status == RuntimeStepStatus.PENDING
        assert step.error is None


@pytest.mark.anyio
async def test_get_stored():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        executor = _make_executor()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        stored = await manager.get_stored("nonexistent")
        assert stored is None

        wf = _make_workflow()
        await manager.start_from_workflow(wf)
        import asyncio
        await asyncio.sleep(0.05)

        found = await manager.get_stored("wf-1")
        assert found is not None
        assert found.workflow_id == "wf-1"


@pytest.mark.anyio
async def test_list_active_and_all():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        executor = _make_executor()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        wf1 = _make_workflow(workflow_id="wf-1", name="WF1")
        wf2 = _make_workflow(workflow_id="wf-2", name="WF2")
        await persistence.save(wf1)
        await persistence.save(wf2)

        all_wf = await manager.list_all()
        assert len(all_wf) == 2


@pytest.mark.anyio
async def test_list_summaries():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        executor = _make_executor()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        wf = _make_workflow()
        await manager.start_from_workflow(wf)
        import asyncio
        await asyncio.sleep(0.1)

        summaries = await manager.list_summaries()
        assert len(summaries) >= 1


@pytest.mark.anyio
async def test_recover():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = _make_persistence(tmp)
        executor = _make_executor()
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)

        running = _make_workflow(workflow_id="wf-run", name="Running")
        running.status = RuntimeWorkflowStatus.RUNNING
        await persistence.save(running)

        recovered = await manager.recover()
        assert recovered == 1
        assert "wf-run" in manager._active_workflows


def test_health():
    persistence = MagicMock()
    persistence.count = MagicMock(return_value=5)
    executor = _make_executor()
    manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
    health = manager.health()
    assert health["status"] == "HEALTHY"
    assert health["details"]["stored_count"] == 5
