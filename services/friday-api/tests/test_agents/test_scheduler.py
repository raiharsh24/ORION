import pytest
import asyncio
import uuid
from typing import Dict, Any, List

from app.agents.scheduler import AgentScheduler
from app.agents.models import AgentTask
from app.events.bus import EventBus


@pytest.mark.anyio
async def test_schedule_once():
    bus = EventBus()
    scheduler = AgentScheduler(event_bus=bus)
    await scheduler.start()

    completed: List[str] = []

    async def handler(task: AgentTask) -> None:
        completed.append(task.task_id)

    job_id = await scheduler.schedule_job(
        name="test-once",
        task_type="echo",
        payload={"msg": "hello"},
        delay_seconds=0.05
    )
    assert job_id is not None
    assert len(scheduler.list_jobs()) == 1

    await asyncio.sleep(0.15)
    assert len(scheduler.list_jobs()) == 0
    await scheduler.shutdown()


@pytest.mark.anyio
async def test_schedule_cancel():
    bus = EventBus()
    scheduler = AgentScheduler(event_bus=bus)
    await scheduler.start()

    job_id = await scheduler.schedule_job(
        name="test-cancel",
        task_type="echo",
        payload={},
        delay_seconds=10.0
    )
    assert scheduler.get_job(job_id) is not None

    cancelled = scheduler.cancel_job(job_id)
    assert cancelled is True
    assert scheduler.get_job(job_id) is None
    assert len(scheduler.list_jobs()) == 0
    await scheduler.shutdown()


@pytest.mark.anyio
async def test_scheduler_health():
    bus = EventBus()
    scheduler = AgentScheduler(event_bus=bus)
    health = scheduler.health()
    assert health["status"] == "HEALTHY"
    assert health["details"]["scheduled_jobs"] == 0
    await scheduler.shutdown()


@pytest.mark.anyio
async def test_scheduler_shutdown_cleans_up_tick_loop():
    """Regression test: start() creates a _tick_loop task, shutdown() must
    cancel it so it does not leak."""
    bus = EventBus()
    scheduler = AgentScheduler(event_bus=bus)
    await scheduler.start()

    assert scheduler._loop_task is not None
    assert not scheduler._loop_task.done()

    await scheduler.shutdown()

    assert scheduler._loop_task.done()
    assert not scheduler._running
    assert len(scheduler._background_tasks) == 0
