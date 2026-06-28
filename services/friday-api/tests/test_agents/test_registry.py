import pytest
import uuid
from typing import Dict, Any

from app.agents.registry import AgentRegistry
from app.agents.base import BaseAgent
from app.agents.models import AgentTask, AgentStatus
from app.events.bus import EventBus


class TestAgent(BaseAgent):
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        return {"ok": True, "type": task.type}


@pytest.mark.anyio
async def test_register_and_list():
    bus = EventBus()
    registry = AgentRegistry(event_bus=bus)

    agent1 = TestAgent(agent_id="a1", name="Agent One", capabilities=["search"])
    agent2 = TestAgent(agent_id="a2", name="Agent Two", capabilities=["compute"])

    await registry.register(agent1)
    await registry.register(agent2)

    assert registry.count() == 2
    infos = registry.list()
    assert len(infos) == 2
    assert {i.agent_id for i in infos} == {"a1", "a2"}

    await registry.unregister("a1")
    assert registry.count() == 1
    assert registry.get("a1") is None


@pytest.mark.anyio
async def test_discover_by_capability():
    bus = EventBus()
    registry = AgentRegistry(event_bus=bus)

    search_agent = TestAgent(agent_id="s1", name="Searcher", capabilities=["search"])
    compute_agent = TestAgent(agent_id="c1", name="Computer", capabilities=["compute"])
    both_agent = TestAgent(agent_id="b1", name="Both", capabilities=["search", "compute"])

    await registry.register(search_agent)
    await registry.register(compute_agent)
    await registry.register(both_agent)

    search_agents = registry.discover("search")
    assert len(search_agents) == 2

    compute_agents = registry.discover("compute")
    assert len(compute_agents) == 2

    unknown = registry.discover("unknown")
    assert len(unknown) == 0


@pytest.mark.anyio
async def test_duplicate_registration_raises():
    bus = EventBus()
    registry = AgentRegistry(event_bus=bus)
    agent = TestAgent(agent_id="dup", name="Dup")
    await registry.register(agent)
    with pytest.raises(ValueError, match="already registered"):
        await registry.register(agent)


@pytest.mark.anyio
async def test_idle_agents():
    bus = EventBus()
    registry = AgentRegistry(event_bus=bus)

    agent = TestAgent(agent_id="idle1", name="Idle Agent", capabilities=["work"])
    await registry.register(agent)
    assert len(registry.get_idle_agents("work")) == 1

    idle_all = registry.get_idle_agents()
    assert len(idle_all) == 1


@pytest.mark.anyio
async def test_registry_health():
    bus = EventBus()
    registry = AgentRegistry(event_bus=bus)
    health = registry.health()
    assert health["status"] == "HEALTHY"
    assert health["details"]["total_agents"] == 0

    agent = TestAgent(agent_id="h1", name="Health Agent", capabilities=["test"])
    await registry.register(agent)
    health = registry.health()
    assert health["details"]["total_agents"] == 1
