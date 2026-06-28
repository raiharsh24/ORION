import pytest
import uuid
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock

from app.workflow_runtime.worker_agent import WorkflowWorkerAgent
from app.agents.models import AgentTask, AgentStatus


@pytest.mark.anyio
async def test_worker_agent_lifecycle():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    assert agent.agent_id == "wf-worker"
    assert agent.name == "Worker"
    assert "tool" in agent.capabilities
    await agent.initialize()
    assert agent.status == AgentStatus.INITIALIZING
    await agent.start()
    assert agent.status == AgentStatus.IDLE
    await agent.shutdown()
    assert agent.status == AgentStatus.STOPPED


@pytest.mark.anyio
async def test_worker_agent_tool_execution():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    mock_ctx = MagicMock()
    mock_ctx.execute_tool = AsyncMock(return_value={"output": "done"})
    agent._context = mock_ctx
    await agent.initialize()
    await agent.start()

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="tool",
        payload={"step_type": "tool", "inputs": {"tool_name": "echo", "args": {"msg": "hi"}}}
    )
    result = await agent.execute_task(task)
    assert result["result"]["output"] == "done"
    assert result["tool"] == "echo"


@pytest.mark.anyio
async def test_worker_agent_llm_execution():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    mock_ctx = MagicMock()
    mock_ctx.generate_llm = AsyncMock(return_value="generated text")
    agent._context = mock_ctx
    await agent.initialize()
    await agent.start()

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="llm",
        payload={"step_type": "llm", "inputs": {"prompt": "Hello"}}
    )
    result = await agent.execute_task(task)
    assert result["response"] == "generated text"


@pytest.mark.anyio
async def test_worker_agent_condition():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="condition",
        payload={"step_type": "condition", "inputs": {"left": 5, "operator": "gt", "right": 3}}
    )
    result = await agent.execute_task(task)
    assert result["condition_result"] is True

    task2 = AgentTask(
        task_id=uuid.uuid4().hex,
        type="condition",
        payload={"step_type": "condition", "inputs": {"left": 1, "operator": "eq", "right": 2}}
    )
    result2 = await agent.execute_task(task2)
    assert result2["condition_result"] is False


@pytest.mark.anyio
async def test_worker_agent_delay():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    import time
    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="delay",
        payload={"step_type": "delay", "inputs": {"seconds": 0.05}}
    )
    start = time.time()
    result = await agent.execute_task(task)
    elapsed = time.time() - start
    assert result["delayed_seconds"] == 0.05
    assert elapsed >= 0.05


@pytest.mark.anyio
async def test_worker_agent_unknown_type():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="unknown",
        payload={"step_type": "unknown", "inputs": {}}
    )
    with pytest.raises(ValueError, match="Unknown step type"):
        await agent.execute_task(task)


@pytest.mark.anyio
async def test_worker_agent_agent_task_recursive():
    agent = WorkflowWorkerAgent(agent_id="wf-worker", name="Worker")
    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="agent_task",
        payload={
            "step_type": "agent_task",
            "inputs": {"sub_type": "condition", "inputs": {"left": "a", "operator": "eq", "right": "a"}}
        }
    )
    result = await agent.execute_task(task)
    assert result["condition_result"] is True
