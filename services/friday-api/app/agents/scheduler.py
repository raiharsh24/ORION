import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timedelta, timezone
from loguru import logger

from app.agents.models import ScheduledJob, AgentTask
from app.agents.events import AgentJobScheduled, AgentJobCompleted


class AgentScheduler:
    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        self._jobs: Dict[str, ScheduledJob] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._loop_task = asyncio.create_task(self._tick_loop())
        logger.info("AgentScheduler started.")

    async def shutdown(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        for job_id, task in self._background_tasks.items():
            task.cancel()
        self._background_tasks.clear()
        logger.info("AgentScheduler shut down.")

    async def schedule_job(
        self,
        name: str,
        task_type: str,
        payload: Dict[str, Any],
        agent_id: Optional[str] = None,
        delay_seconds: Optional[float] = None,
        interval_seconds: Optional[float] = None,
        max_runs: Optional[int] = None
    ) -> str:
        job_id = uuid.uuid4().hex
        schedule_type = "INTERVAL" if interval_seconds else "ONCE"

        next_run = datetime.now(timezone.utc)
        if delay_seconds:
            next_run += timedelta(seconds=delay_seconds)
        if interval_seconds and not delay_seconds:
            next_run += timedelta(seconds=interval_seconds)

        job = ScheduledJob(
            job_id=job_id,
            agent_id=agent_id,
            name=name,
            task_type=task_type,
            payload=payload,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            delay_seconds=delay_seconds,
            max_runs=max_runs,
            next_run=next_run,
            created_at=datetime.now(timezone.utc)
        )
        self._jobs[job_id] = job
        self._event_bus and self._event_bus.publish_background(AgentJobScheduled(job_id, name, schedule_type))
        logger.info(f"AgentScheduler: scheduled job '{name}' ({job_id}) type={schedule_type}")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.pop(job_id, None)
        if job:
            bgt = self._background_tasks.pop(job_id, None)
            if bgt:
                bgt.cancel()
            logger.info(f"AgentScheduler: cancelled job '{job.name}' ({job_id})")
            return True
        return False

    def list_jobs(self) -> List[ScheduledJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        return self._jobs.get(job_id)

    async def execute_once(
        self,
        handler: Callable[[AgentTask], Awaitable[Any]],
        task: AgentTask
    ) -> None:
        job_id = task.task_id
        try:
            bg_task = asyncio.create_task(handler(task))
            self._background_tasks[job_id] = bg_task
            await bg_task
            self._event_bus and self._event_bus.publish_background(AgentJobCompleted(job_id, success=True))
        except Exception as e:
            logger.error(f"AgentScheduler: job {job_id} failed: {e}")
            self._event_bus and self._event_bus.publish_background(AgentJobCompleted(job_id, success=False))
        finally:
            self._background_tasks.pop(job_id, None)

    async def _tick_loop(self) -> None:
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                due_jobs = [
                    job for job in self._jobs.values()
                    if job.enabled and job.next_run and job.next_run <= now
                ]
                for job in due_jobs:
                    if job.schedule_type == "INTERVAL":
                        if job.max_runs and job.run_count >= job.max_runs:
                            self._jobs.pop(job.job_id, None)
                            continue
                        job.run_count += 1
                        job.next_run = now + timedelta(seconds=job.interval_seconds or 60)
                    elif job.schedule_type == "ONCE":
                        self._jobs.pop(job.job_id, None)

                    logger.debug(f"AgentScheduler: due job '{job.name}' ({job.job_id})")
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"AgentScheduler tick error: {e}")
                await asyncio.sleep(5)



    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "message": "AgentScheduler operational.",
            "details": {
                "scheduled_jobs": len(self._jobs),
                "active_background_tasks": len(self._background_tasks),
                "running": self._running
            }
        }
