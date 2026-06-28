import asyncio
from typing import Dict, List, Optional
from loguru import logger
from app.scheduler.jobs import ScheduledJob
from app.scheduler.triggers import TriggerType


class FridayScheduler:
    """
    Orchestrates time-based execution of scheduled jobs.
    """
    def __init__(self) -> None:
        self.jobs: Dict[str, ScheduledJob] = {}
        self._tick_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tick_task = asyncio.create_task(self._tick_loop())
        logger.info("Scheduler tick loop started")

    async def _tick_loop(self) -> None:
        try:
            while self._running:
                now = asyncio.get_event_loop().time()
                for job in list(self.jobs.values()):
                    try:
                        if job.trigger.should_fire(now):
                            logger.info(f"Scheduler: firing job '{job.job_id}' (workflow '{job.workflow_id}')")
                            job.last_run_timestamp = now
                            job.success_count += 1
                    except Exception as e:
                        logger.error(f"Scheduler: job '{job.job_id}' trigger check failed: {e}")
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Scheduler tick loop cancelled")
        finally:
            self._running = False

    async def schedule_job(self, job: ScheduledJob) -> None:
        self.jobs[job.job_id] = job
        logger.info(f"Scheduled job '{job.job_id}' (workflow '{job.workflow_id}')")

    async def stop(self) -> None:
        self._running = False
        if self._tick_task and not self._tick_task.done():
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None
        logger.info("Scheduler stopped")
