import pytest
import uuid
from typing import Dict, Any, List

from app.agents.bus import AgentMessageBus
from app.agents.models import AgentMessage
from app.events.bus import EventBus


@pytest.mark.anyio
async def test_send_and_receive():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    received: List[AgentMessage] = []

    async def handler(msg: AgentMessage) -> None:
        received.append(msg)

    msg_bus.subscribe("agent-1", handler)

    msg = AgentMessage(
        message_id=uuid.uuid4().hex,
        sender="coordinator",
        recipient="agent-1",
        type="COMMAND",
        payload={"action": "greet"}
    )
    await msg_bus.send(msg)
    assert len(received) == 1
    assert received[0].payload["action"] == "greet"


@pytest.mark.anyio
async def test_broadcast():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    received: List[str] = []

    async def handler_a(msg: AgentMessage) -> None:
        received.append("a")

    async def handler_b(msg: AgentMessage) -> None:
        received.append("b")

    msg_bus.subscribe("agent-a", handler_a)
    msg_bus.subscribe("agent-b", handler_b)

    msg = AgentMessage(
        message_id=uuid.uuid4().hex,
        sender="coordinator",
        type="BROADCAST",
        payload={"info": "all-agents"}
    )
    await msg_bus.broadcast(msg)
    assert len(received) == 2
    assert "a" in received
    assert "b" in received


@pytest.mark.anyio
async def test_request_response():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)

    async def handler(msg: AgentMessage) -> None:
        response = msg_bus.respond(msg, {"result": "ok"})
        await msg_bus.send(response)

    msg_bus.subscribe("agent-1", handler)

    request = AgentMessage(
        message_id=uuid.uuid4().hex,
        sender="client",
        recipient="agent-1",
        type="REQUEST",
        payload={"query": "status"}
    )
    response = await msg_bus.request("agent-1", request, timeout=5.0)
    assert response is not None
    assert response.payload["result"] == "ok"
    assert response.correlation_id == request.correlation_id


@pytest.mark.anyio
async def test_request_timeout():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)

    request = AgentMessage(
        message_id=uuid.uuid4().hex,
        sender="client",
        recipient="ghost-agent",
        type="REQUEST",
        payload={"query": "ping"}
    )
    response = await msg_bus.request("ghost-agent", request, timeout=0.1)
    assert response is None


@pytest.mark.anyio
async def test_unsubscribe():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    received: List[AgentMessage] = []

    async def handler(msg: AgentMessage) -> None:
        received.append(msg)

    msg_bus.subscribe("agent-1", handler)
    msg_bus.unsubscribe("agent-1", handler)

    msg = AgentMessage(
        message_id=uuid.uuid4().hex,
        sender="coordinator",
        recipient="agent-1",
        type="COMMAND",
        payload={}
    )
    await msg_bus.send(msg)
    assert len(received) == 0


@pytest.mark.anyio
async def test_bus_health():
    bus = EventBus()
    msg_bus = AgentMessageBus(event_bus=bus)
    health = msg_bus.health()
    assert health["status"] == "HEALTHY"
    assert health["details"]["subscribers"] == 0
