import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from typing import Dict, Any

from app.workflow_runtime.executor import WorkflowRuntimeExecutor
from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RuntimeStepStatus,
    ExecutionPlanInput, RetryPolicy
)
from app.workflow_runtime.checkpoints import CheckpointManager
from app.agents.models import AgentTask


@pytest.mark.anyio
async def test_execute_step_success():
    coordinator = MagicMock()
    coordinator.delegate = AsyncMock(return_value={"output": "success"})
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)

    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    step = RuntimeStep(step_id="s1", name="Step 1", step_type="tool",
                       input={"cmd": "echo"}, retry_policy=RetryPolicy())

    result = await executor.execute_step(wf, step, {})
    assert result == {"output": "success"}
    assert step.status == RuntimeStepStatus.COMPLETED
    assert step.started_at is not None
    assert step.completed_at is not None


@pytest.mark.anyio
async def test_execute_step_failure():
    coordinator = MagicMock()
    coordinator.delegate = AsyncMock(side_effect=RuntimeError("fail"))
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)

    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    step = RuntimeStep(step_id="s1", name="Step 1", step_type="tool",
                       input={}, retry_policy=RetryPolicy())

    with pytest.raises(RuntimeError, match="fail"):
        await executor.execute_step(wf, step, {})
    assert step.status == RuntimeStepStatus.FAILED
    assert step.error == "fail"


@pytest.mark.anyio
async def test_execute_step_with_variable_resolution():
    coordinator = MagicMock()
    coordinator.delegate = AsyncMock(side_effect=lambda task: task.payload["inputs"])

    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)
    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    step = RuntimeStep(step_id="s1", name="Step 1", step_type="tool",
                       input={"cmd": "echo {{var1}}", "path": "{{s1.output.dir}}"},
                       retry_policy=RetryPolicy())

    variables = {"var1": "hello", "s1.output": {"dir": "/tmp"}}
    result = await executor.execute_step(wf, step, variables)
    assert result["cmd"] == "echo hello"
    assert result["path"] == "/tmp"


@pytest.mark.anyio
async def test_execute_step_with_checkpoint():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        coordinator = MagicMock()
        coordinator.delegate = AsyncMock(return_value={"done": True})
        cp = CheckpointManager(persist_dir=tmp)
        executor = WorkflowRuntimeExecutor(
            agent_coordinator=coordinator, checkpoint_manager=cp
        )

        wf = RuntimeWorkflow(workflow_id="wf-cp", name="Test")
        step = RuntimeStep(step_id="s1", name="Step 1", step_type="tool",
                           input={}, retry_policy=RetryPolicy())

        result = await executor.execute_step(wf, step, {})
        assert result == {"done": True}

        checkpoint = await cp.load_checkpoint("wf-cp", "s1")
        assert checkpoint is not None
        assert checkpoint["status"] == "COMPLETED"


def test_build_from_plan():
    plan = ExecutionPlanInput(
        plan_id="plan-1",
        goal="Test deployment",
        steps=[
            {"step_id": "s1", "name": "Build", "type": "tool",
             "input": {"cmd": "build"}, "depends_on": ["s0"]},
            {"step_id": "s2", "name": "Deploy", "type": "tool",
             "input": {"cmd": "deploy"}},
        ],
        variables={"env": "prod"},
        metadata={"author": "test"},
    )
    coordinator = MagicMock()
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)
    wf = executor.build_from_plan(plan)

    assert wf.workflow_id == "plan-plan-1"
    assert wf.name == "Test deployment"
    assert len(wf.steps) == 2
    assert "s1" in wf.steps
    assert "s2" in wf.steps
    assert wf.steps["s1"].depends_on == ["s0"]
    assert wf.variables == {"env": "prod"}
    assert wf.metadata == {"author": "test"}


@pytest.mark.anyio
async def test_execute_parallel_steps():
    coordinator = MagicMock()
    coordinator.delegate = AsyncMock(side_effect=[
        {"step": "s1"}, {"step": "s2"}
    ])
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)
    wf = RuntimeWorkflow(workflow_id="wf-par", name="Parallel")
    s1 = RuntimeStep(step_id="s1", name="S1", step_type="tool",
                     input={}, retry_policy=RetryPolicy())
    s2 = RuntimeStep(step_id="s2", name="S2", step_type="tool",
                     input={}, retry_policy=RetryPolicy())

    results = await executor.execute_parallel_steps(wf, [s1, s2], {})
    assert results["s1"]["step"] == "s1"
    assert results["s2"]["step"] == "s2"
    assert s1.status == RuntimeStepStatus.COMPLETED
    assert s2.status == RuntimeStepStatus.COMPLETED


def test_health():
    coordinator = MagicMock()
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)
    health = executor.health()
    assert health["status"] == "HEALTHY"
