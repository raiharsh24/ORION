import pytest
import asyncio
import uuid
from typing import Dict, Any

from app.agents.recovery import CircuitBreaker, RetryHandler, DeadLetterQueue
from app.agents.models import CircuitBreakerState, AgentMessage, AgentTask
from app.events.bus import EventBus


@pytest.mark.anyio
async def test_circuit_breaker_closed():
    cb = CircuitBreaker(name="test-cb", failure_threshold=3, reset_timeout=60.0)

    async def success() -> str:
        return "ok"

    result = await cb.call(success)
    assert result == "ok"
    assert cb.state == CircuitBreakerState.CLOSED


@pytest.mark.anyio
async def test_circuit_breaker_trips():
    cb = CircuitBreaker(name="test-trip", failure_threshold=3, reset_timeout=60.0)

    async def fail() -> str:
        raise RuntimeError("fail")

    for i in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(fail)

    assert cb.state == CircuitBreakerState.OPEN


@pytest.mark.anyio
async def test_circuit_breaker_rejects_when_open():
    cb = CircuitBreaker(name="test-reject", failure_threshold=2, reset_timeout=60.0)

    async def fail() -> str:
        raise RuntimeError("fail")

    for i in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)

    assert cb.state == CircuitBreakerState.OPEN

    async def success() -> str:
        return "ok"

    with pytest.raises(RuntimeError, match="OPEN"):
        await cb.call(success)


@pytest.mark.anyio
async def test_circuit_breaker_half_open_recovery():
    cb = CircuitBreaker(
        name="test-halfopen", failure_threshold=2,
        reset_timeout=0.1, half_open_max_retries=2
    )

    async def fail() -> str:
        raise RuntimeError("fail")

    for i in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    assert cb.state == CircuitBreakerState.OPEN

    await asyncio.sleep(0.15)

    async def success() -> str:
        return "ok"

    result = await cb.call(success)
    assert result == "ok"
    assert cb._half_open_retries == 1

    result = await cb.call(success)
    assert result == "ok"

    assert cb.state == CircuitBreakerState.CLOSED


@pytest.mark.anyio
async def test_retry_handler_success():
    handler = RetryHandler(max_retries=3, base_delay=0.01)
    call_count = 0

    async def might_fail() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("not yet")
        return "success"

    result = await handler.execute(might_fail)
    assert result == "success"
    assert call_count == 3


@pytest.mark.anyio
async def test_retry_handler_exhausted():
    handler = RetryHandler(max_retries=2, base_delay=0.01)

    async def always_fails() -> str:
        raise RuntimeError("always")

    with pytest.raises(RuntimeError, match="always"):
        await handler.execute(always_fails)


@pytest.mark.anyio
async def test_dead_letter_queue():
    dlq = DeadLetterQueue()
    msg = AgentMessage(
        message_id=uuid.uuid4().hex,
        sender="agent-1",
        recipient="nonexistent",
        type="COMMAND",
        payload={}
    )
    await dlq.put(msg, "Agent not found")
    assert dlq.count == 1

    entry = dlq.entries[0]
    assert entry.error == "Agent not found"

    recovered = await dlq.retry(0)
    assert recovered is not None
    assert recovered.message_id == msg.message_id
    assert dlq.count == 0


@pytest.mark.anyio
async def test_dead_letter_retry_all():
    dlq = DeadLetterQueue()
    for i in range(3):
        msg = AgentMessage(
            message_id=uuid.uuid4().hex,
            sender=f"agent-{i}",
            recipient="x",
            type="COMMAND",
            payload={}
        )
        await dlq.put(msg, f"Error {i}")
    assert dlq.count == 3

    messages = await dlq.retry_all()
    assert len(messages) == 3
    assert dlq.count == 0
