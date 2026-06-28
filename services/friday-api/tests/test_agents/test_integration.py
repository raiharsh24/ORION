import pytest
import uuid
from typing import Dict, Any

from app.kernel import FridayKernel, FridayKernelConfig
from app.agents.base import BaseAgent
from app.agents.models import AgentTask, AgentInfo, CoordinatorResult
from app.events.events import FridayEvent


class IntegrationAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        return {
            "echo": task.payload,
            "agent": self._agent_id,
            "type": task.type
        }


@pytest.mark.anyio
async def test_kernel_boot_with_agent_runtime():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    assert kernel.get_service("agent_message_bus") is not None
    assert kernel.get_service("agent_registry") is not None
    assert kernel.get_service("agent_scheduler") is not None
    assert kernel.get_service("agent_telemetry") is not None
    assert kernel.get_service("shared_context") is not None
    assert kernel.get_service("agent_coordinator") is not None

    await kernel.shutdown()


@pytest.mark.anyio
async def test_agent_register_and_route_via_kernel():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    registry = kernel.get_service("agent_registry")
    coordinator = kernel.get_service("agent_coordinator")

    agent = IntegrationAgent(
        agent_id="int-agent",
        name="Integration Agent",
        capabilities=["test", "echo"]
    )
    await registry.register(agent)

    infos = registry.list()
    assert len(infos) >= 1
    registered_ids = [i.agent_id for i in infos]
    assert "int-agent" in registered_ids
    int_agent_info = next(i for i in infos if i.agent_id == "int-agent")
    assert "echo" in int_agent_info.capabilities

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="echo",
        payload={"message": "integration test"}
    )
    result = await coordinator.delegate(task)
    assert result["echo"]["message"] == "integration test"
    assert result["agent"] == "int-agent"

    await kernel.shutdown()


@pytest.mark.anyio
async def test_kernel_health_includes_agents():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    health = kernel.health()
    assert health.agents is not None
    assert health.agents.name == "agents"
    assert health.agents.status.value == "HEALTHY"

    await kernel.shutdown()


@pytest.mark.anyio
async def test_shared_context_via_kernel():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    ctx = kernel.get_service("shared_context")
    assert ctx is not None
    assert ctx.kernel is kernel

    engine_health = ctx.health()
    assert engine_health["status"] == "HEALTHY"

    await kernel.shutdown()


@pytest.mark.anyio
async def test_agent_telemetry_collection():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    registry = kernel.get_service("agent_registry")
    coordinator = kernel.get_service("agent_coordinator")
    telemetry = kernel.get_service("agent_telemetry")

    agent = IntegrationAgent(
        agent_id="telemetry-agent",
        name="Telemetry Test",
        capabilities=["work"]
    )
    await registry.register(agent)

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="work",
        payload={"task": "metrics"}
    )
    await coordinator.delegate(task)

    metrics = telemetry.get_agent_metrics("telemetry-agent")
    assert metrics is not None
    assert metrics.tasks_processed >= 1
    assert metrics.tasks_succeeded >= 1

    await kernel.shutdown()


@pytest.mark.anyio
async def test_event_bus_agent_events():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    event_bus = kernel.get_service("event_bus")
    received_events: list = []

    async def capture(event: FridayEvent) -> None:
        received_events.append(event.topic)

    event_bus.subscribe("Agent*", capture)
    event_bus.subscribe("AgentTask*", capture)

    registry = kernel.get_service("agent_registry")
    coordinator = kernel.get_service("agent_coordinator")

    agent = IntegrationAgent(
        agent_id="event-agent",
        name="Event Test",
        capabilities=["test"]
    )
    await registry.register(agent)

    task = AgentTask(
        task_id=uuid.uuid4().hex,
        type="test",
        payload={"event": "check"}
    )
    await coordinator.delegate(task)
    await kernel.shutdown()
