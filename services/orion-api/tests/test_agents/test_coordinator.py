import pytest
import uuid
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.agents.registry import AgentRegistry
from app.agents.bus import AgentMessageBus
from app.agents.scheduler import AgentScheduler
from app.agents.telemetry import AgentTelemetry
from app.agents.coordinator import AgentCoordinator
from app.agents.models import AgentTask, AgentStatus, CoordinatorResult
from app.events.bus import EventBus


class FastAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        return {"processed": task.type, "payload": task.payload}


class SlowAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        import asyncio
        await asyncio.sleep(0.2)
        return {"slow": "done"}


@pytest.mark.anyio
async def test_route_task():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    registry = AgentRegistry(event_bus=bus)
    scheduler = AgentScheduler(event_bus=bus)
    telemetry = AgentTelemetry()

    coordinator = AgentCoordinator(
        registry=registry,
        message_bus=msg_bus,
        scheduler=scheduler,
        telemetry=telemetry,
        event_bus=bus
    )

    agent = FastAgent(agent_id="router-agent", name="Router Test", capabilities=["search"])
    await registry.register(agent)

    task = AgentTask(task_id=uuid.uuid4().hex, type="search", payload={"q": "hello"})
    agent_id = await coordinator.route_task(task)
    assert agent_id == "router-agent"


@pytest.mark.anyio
async def test_delegate_task():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    registry = AgentRegistry(event_bus=bus)
    scheduler = AgentScheduler(event_bus=bus)
    telemetry = AgentTelemetry()

    coordinator = AgentCoordinator(
        registry=registry,
        message_bus=msg_bus,
        scheduler=scheduler,
        telemetry=telemetry,
        event_bus=bus
    )

    agent = FastAgent(agent_id="delegate-agent", name="Delegate Test", capabilities=["work"])
    await registry.register(agent)

    task = AgentTask(task_id=uuid.uuid4().hex, type="work", payload={"cmd": "do"})
    result = await coordinator.delegate(task)
    assert result["processed"] == "work"
    assert result["payload"]["cmd"] == "do"


@pytest.mark.anyio
async def test_delegate_no_agent():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    registry = AgentRegistry(event_bus=bus)
    scheduler = AgentScheduler(event_bus=bus)
    telemetry = AgentTelemetry()

    coordinator = AgentCoordinator(
        registry=registry,
        message_bus=msg_bus,
        scheduler=scheduler,
        telemetry=telemetry,
        event_bus=bus
    )

    task = AgentTask(task_id=uuid.uuid4().hex, type="unknown")
    with pytest.raises(RuntimeError, match="Could not route"):
        await coordinator.delegate(task)


@pytest.mark.anyio
async def test_execute_parallel():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    registry = AgentRegistry(event_bus=bus)
    scheduler = AgentScheduler(event_bus=bus)
    telemetry = AgentTelemetry()

    coordinator = AgentCoordinator(
        registry=registry,
        message_bus=msg_bus,
        scheduler=scheduler,
        telemetry=telemetry,
        event_bus=bus
    )

    agent = FastAgent(agent_id="parallel-agent", name="Parallel Test", capabilities=["task"])
    await registry.register(agent)

    tasks = [
        AgentTask(task_id=uuid.uuid4().hex, type="task"),
        AgentTask(task_id=uuid.uuid4().hex, type="task"),
    ]
    result = await coordinator.execute_parallel(tasks)
    assert result.success is True
    assert len(result.results) == 2
    assert len(result.errors) == 0


@pytest.mark.anyio
async def test_cancel_task():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    registry = AgentRegistry(event_bus=bus)
    scheduler = AgentScheduler(event_bus=bus)
    telemetry = AgentTelemetry()

    coordinator = AgentCoordinator(
        registry=registry,
        message_bus=msg_bus,
        scheduler=scheduler,
        telemetry=telemetry,
        event_bus=bus
    )

    agent = FastAgent(agent_id="cancel-agent", name="Cancel Test", capabilities=["x"])
    await registry.register(agent)

    task = AgentTask(task_id=uuid.uuid4().hex, type="x")
    agent._current_task = task

    cancelled = await coordinator.cancel_task(task.task_id)
    assert cancelled is True


@pytest.mark.anyio
async def test_coordinator_health():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    registry = AgentRegistry(event_bus=bus)
    scheduler = AgentScheduler(event_bus=bus)
    telemetry = AgentTelemetry()

    coordinator = AgentCoordinator(
        registry=registry,
        message_bus=msg_bus,
        scheduler=scheduler,
        telemetry=telemetry,
        event_bus=bus
    )
    health = coordinator.health()
    assert health["status"] == "HEALTHY"
