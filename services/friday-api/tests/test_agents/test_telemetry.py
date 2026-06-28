import pytest
import uuid
from datetime import datetime, timezone

from app.agents.telemetry import AgentTelemetry
from app.agents.models import AgentTask, AgentTrace
from app.events.bus import EventBus


@pytest.mark.anyio
async def test_trace_lifecycle():
    telemetry = AgentTelemetry()
    span_id = telemetry.start_trace(
        agent_id="agent-1",
        operation="test-operation",
        parent_span_id=None
    )
    assert span_id is not None
    trace = telemetry.get_trace(span_id)
    assert trace is not None
    assert trace.operation == "test-operation"
    assert trace.agent_id == "agent-1"
    assert trace.status == "OK"

    telemetry.end_trace(span_id, status="OK")
    trace = telemetry.get_trace(span_id)
    assert trace.ended_at is not None
    assert trace.duration_ms is not None
    assert trace.duration_ms >= 0


@pytest.mark.anyio
async def test_trace_with_parent():
    telemetry = AgentTelemetry()
    parent_id = telemetry.start_trace("agent-1", "parent-op")
    child_id = telemetry.start_trace("agent-1", "child-op", parent_span_id=parent_id)

    child = telemetry.get_trace(child_id)
    assert child.parent_span_id == parent_id


@pytest.mark.anyio
async def test_agent_metrics():
    telemetry = AgentTelemetry()
    task = AgentTask(
        task_id=uuid.uuid4().hex,
        agent_id="agent-1",
        type="echo",
        status="COMPLETED"
    )
    telemetry.record_task_metrics(task, duration_ms=150.0, success=True)

    metrics = telemetry.get_agent_metrics("agent-1")
    assert metrics is not None
    assert metrics.tasks_processed == 1
    assert metrics.tasks_succeeded == 1
    assert metrics.total_duration_ms == 150.0
    assert metrics.avg_duration_ms == 150.0


@pytest.mark.anyio
async def test_agent_metrics_failure():
    telemetry = AgentTelemetry()
    task = AgentTask(
        task_id=uuid.uuid4().hex,
        agent_id="agent-2",
        type="fail",
        status="FAILED"
    )
    telemetry.record_task_metrics(task, duration_ms=50.0, success=False)

    metrics = telemetry.get_agent_metrics("agent-2")
    assert metrics is not None
    assert metrics.tasks_failed == 1
    assert metrics.tasks_processed == 1


@pytest.mark.anyio
async def test_record_error_and_message():
    telemetry = AgentTelemetry()
    telemetry.record_error("agent-1")
    telemetry.record_message("agent-1", "sent")
    telemetry.record_message("agent-1", "received")

    metrics = telemetry.get_agent_metrics("agent-1")
    assert metrics.errors == 1
    assert metrics.messages_sent == 1
    assert metrics.messages_received == 1


@pytest.mark.anyio
async def test_clear():
    telemetry = AgentTelemetry()
    telemetry.start_trace("agent-1", "op")
    assert len(telemetry.traces) == 1
    telemetry.clear_traces()
    assert len(telemetry.traces) == 0

    task = AgentTask(task_id=uuid.uuid4().hex, agent_id="agent-1", type="test")
    telemetry.record_task_metrics(task, 100.0, True)
    assert len(telemetry.metrics) == 1
    telemetry.clear_metrics()
    assert len(telemetry.metrics) == 0


@pytest.mark.anyio
async def test_telemetry_health():
    telemetry = AgentTelemetry()
    health = telemetry.health()
    assert health["status"] == "HEALTHY"
