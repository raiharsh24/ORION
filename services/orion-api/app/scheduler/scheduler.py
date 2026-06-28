from typing import Dict, List
from app.scheduler.jobs import ScheduledJob

class OrionScheduler:
    """
    Orchestrates time-based execution of scheduled jobs.

    TODO:
    - Support starting and stopping the background scheduling thread/loop
    - Map job schedules and check triggers periodically
    - Execute workflows upon trigger match events
    """
    def __init__(self) -> None:
        self.jobs: Dict[str, ScheduledJob] = {}

    async def start(self) -> None:
        """
        Starts the background tick scheduler loop.
        """
        # TODO: Launch asynchronous schedule check thread
        pass

    async def schedule_job(self, job: ScheduledJob) -> None:
        """
        Saves a job in the active schedules map.

        Args:
            job (ScheduledJob): Job properties to register.
        """
        self.jobs[job.job_id] = job

    async def stop(self) -> None:
        """
        Halts scheduler background checks.
        """
        # TODO: Safely join threads and cleanup
        pass
