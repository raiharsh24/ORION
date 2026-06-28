import pytest
import uuid
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.agents.models import AgentStatus, AgentTask, AgentMessage


class EchoAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        return {"echo": task.payload, "agent": self._agent_id}


class FailingAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        raise RuntimeError("Intentional failure")


class TimeoutAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        import asyncio
        await asyncio.sleep(10)
        return {"ok": True}


@pytest.mark.anyio
async def test_agent_lifecycle():
    agent = EchoAgent(agent_id="test-1", name="Test Echo", capabilities=["echo"])
    assert agent.status == AgentStatus.STOPPED
    assert agent.agent_id == "test-1"
    assert agent.name == "Test Echo"
    assert "echo" in agent.capabilities

    await agent.initialize()
    assert agent.status == AgentStatus.INITIALIZING

    await agent.start()
    assert agent.status == AgentStatus.IDLE

    info = agent.info
    assert info.agent_id == "test-1"
    assert info.status == AgentStatus.IDLE
    assert info.tasks_completed == 0

    await agent.shutdown()
    assert agent.status == AgentStatus.STOPPED


@pytest.mark.anyio
async def test_agent_pause_resume():
    agent = EchoAgent(agent_id="test-pause", name="Pause Test", capabilities=["echo"])
    await agent.initialize()
    await agent.start()

    await agent.pause()
    assert agent.status == AgentStatus.PAUSED

    await agent.resume()
    assert agent.status == AgentStatus.IDLE

    await agent.shutdown()


@pytest.mark.anyio
async def test_agent_process_task_success():
    agent = EchoAgent(agent_id="test-task", name="Task Test", capabilities=["echo"])
    await agent.initialize()
    await agent.start()

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="echo",
        payload={"message": "hello"}
    )
    result = await agent.process_task(task)
    assert result["echo"]["message"] == "hello"
    assert result["agent"] == "test-task"
    assert task.status == "COMPLETED"
    assert agent.status == AgentStatus.IDLE
    assert agent.info.tasks_completed == 1


@pytest.mark.anyio
async def test_agent_process_task_failure():
    agent = FailingAgent(agent_id="test-fail", name="Fail Test", capabilities=["fail"])
    await agent.initialize()
    await agent.start()

    task = AgentTask(task_id=uuid.uuid4().hex, type="fail")
    with pytest.raises(RuntimeError, match="Intentional failure"):
        await agent.process_task(task)
    assert task.status == "FAILED"
    assert agent.info.tasks_failed == 1


@pytest.mark.anyio
async def test_agent_process_task_timeout():
    agent = TimeoutAgent(agent_id="test-timeout", name="Timeout Test", capabilities=["slow"])
    await agent.initialize()
    await agent.start()

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="slow",
        timeout=0.1
    )
    with pytest.raises(TimeoutError):
        await agent.process_task(task)
    assert task.status == "TIMEOUT"


@pytest.mark.anyio
async def test_agent_rejects_when_stopped():
    agent = EchoAgent(agent_id="test-reject", name="Reject Test", capabilities=["echo"])
    task = AgentTask(task_id=uuid.uuid4().hex, type="echo")
    with pytest.raises(RuntimeError, match="stopped"):
        await agent.process_task(task)


@pytest.mark.anyio
async def test_agent_cancel_task():
    agent = EchoAgent(agent_id="test-cancel", name="Cancel Test", capabilities=["echo"])
    await agent.initialize()
    await agent.start()

    task = AgentTask(task_id=uuid.uuid4().hex, type="echo")
    agent._current_task = task
    await agent.cancel_task()
    assert task.status == "CANCELLED"
    assert agent.status == AgentStatus.IDLE
    assert agent._current_task is None
