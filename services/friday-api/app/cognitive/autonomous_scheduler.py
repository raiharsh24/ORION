import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Set, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ScheduledMission:
    mission_id: str
    objective: str
    mission_type: str = "once"
    interval_seconds: float = 0.0
    priority: float = 5.0
    status: str = "pending"
    depends_on: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    scheduled_at: float = 0.0
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    max_runs: int = 0
    max_retries: int = 3
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionSlot:
    mission_id: str
    objective: str
    priority: float
    estimated_duration_ms: float = 10000.0
    scheduled_at: float = 0.0

    @property
    def is_overdue(self) -> bool:
        return self.scheduled_at > 0 and time.time() > self.scheduled_at


class AutonomousScheduler:
    POLL_INTERVAL = 2.0

    def __init__(self, mission_executor: Any = None,
                 adaptive_scheduler: Any = None) -> None:
        self._executor = mission_executor
        self._adaptive = adaptive_scheduler
        self._missions: Dict[str, ScheduledMission] = {}
        self._running: Set[str] = set()
        self._handlers: Dict[str, Callable] = {}
        self._task: Optional[asyncio.Task] = None
        self._running_flag = False
        self._total_executed = 0
        self._total_deferred = 0
        self._total_skipped = 0

    def register_handler(self, mission_type: str,
                          handler: Callable) -> None:
        self._handlers[mission_type] = handler

    def schedule_once(self, objective: str,
                      delay_seconds: float = 0.0,
                      priority: float = 5.0,
                      depends_on: Optional[List[str]] = None,
                      mission_type: str = "once") -> ScheduledMission:
        mission = ScheduledMission(
            mission_id=str(uuid.uuid4()),
            objective=objective,
            mission_type=mission_type,
            priority=priority,
            depends_on=depends_on or [],
            scheduled_at=time.time() + delay_seconds if delay_seconds > 0 else time.time(),
            next_run=time.time() + delay_seconds if delay_seconds > 0 else time.time(),
        )
        self._missions[mission.mission_id] = mission
        logger.info(
            f"AutonomousScheduler: Scheduled '{objective[:60]}' "
            f"(delay={delay_seconds}s, priority={priority})"
        )
        return mission

    def schedule_recurring(self, objective: str,
                            interval_seconds: float,
                            priority: float = 5.0,
                            max_runs: int = 0,
                            start_delay: float = 0.0) -> ScheduledMission:
        mission = ScheduledMission(
            mission_id=str(uuid.uuid4()),
            objective=objective,
            mission_type="recurring",
            interval_seconds=interval_seconds,
            priority=priority,
            max_runs=max_runs,
            scheduled_at=time.time() + start_delay,
            next_run=time.time() + start_delay,
        )
        self._missions[mission.mission_id] = mission
        logger.info(
            f"AutonomousScheduler: Recurring '{objective[:60]}' "
            f"(every {interval_seconds}s, max={max_runs or 'infinite'})"
        )
        return mission

    def cancel(self, mission_id: str) -> bool:
        mission = self._missions.get(mission_id)
        if not mission:
            return False
        mission.status = "cancelled"
        self._running.discard(mission_id)
        return True

    def get_due_missions(self) -> List[ScheduledMission]:
        now = time.time()
        due = []
        for m in self._missions.values():
            if m.status != "pending" and m.status != "running":
                continue
            if m.max_runs > 0 and m.run_count >= m.max_runs:
                continue
            if m.next_run is None or now < m.next_run:
                continue
            if not self._dependencies_satisfied(m):
                continue
            if m.mission_id in self._running:
                continue
            due.append(m)
        return sorted(due, key=lambda m: (-m.priority, m.next_run or 0))

    def _dependencies_satisfied(self, mission: ScheduledMission) -> bool:
        for dep_id in mission.depends_on:
            dep = self._missions.get(dep_id)
            if not dep or dep.status != "completed":
                return False
        return True

    async def execute_due(self) -> List[str]:
        due = self.get_due_missions()
        if not due:
            return []

        executed = []
        for mission in due:
            mission.status = "running"
            self._running.add(mission.mission_id)

            handler = self._handlers.get(mission.mission_type)
            try:
                if handler:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(mission)
                    else:
                        handler(mission)

                mission.run_count += 1
                mission.last_run = time.time()
                mission.status = "completed"
                self._total_executed += 1
                executed.append(mission.mission_id)
                logger.info(
                    f"AutonomousScheduler: Executed '{mission.objective[:60]}'"
                )

                if mission.mission_type == "recurring":
                    if mission.max_runs == 0 or mission.run_count < mission.max_runs:
                        mission.status = "pending"
                        mission.next_run = time.time() + mission.interval_seconds
                        mission.retry_count = 0

            except Exception as e:
                mission.retry_count += 1
                logger.error(
                    f"AutonomousScheduler: Failed '{mission.objective[:60]}': {e}"
                )
                if mission.retry_count >= mission.max_retries:
                    mission.status = "failed"
                    logger.warning(
                        f"AutonomousScheduler: Gave up on '{mission.objective[:60]}' "
                        f"after {mission.retry_count} retries"
                    )
                else:
                    mission.status = "pending"
                    mission.next_run = time.time() + (mission.interval_seconds or 60)
            finally:
                self._running.discard(mission.mission_id)

        return executed

    async def start_background(self) -> None:
        if self._running_flag:
            return
        self._running_flag = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("AutonomousScheduler: Background loop started")

    async def _run_loop(self) -> None:
        while self._running_flag:
            try:
                await self.execute_due()
            except Exception as e:
                logger.error(f"AutonomousScheduler loop error: {e}")
            await asyncio.sleep(self.POLL_INTERVAL)

    async def shutdown(self) -> None:
        self._running_flag = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AutonomousScheduler: Shut down")

    def get_pending(self) -> List[Dict[str, Any]]:
        return [
            {
                "mission_id": m.mission_id,
                "objective": m.objective[:80],
                "type": m.mission_type,
                "priority": m.priority,
                "status": m.status,
                "next_run": m.next_run,
                "run_count": m.run_count,
                "retry_count": m.retry_count,
            }
            for m in sorted(
                self._missions.values(),
                key=lambda x: (-x.priority, x.next_run or 0),
            )
            if m.status in ("pending", "running")
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_scheduled": len(self._missions),
            "total_executed": self._total_executed,
            "total_deferred": self._total_deferred,
            "total_skipped": self._total_skipped,
            "running_now": len(self._running),
            "pending_count": sum(
                1 for m in self._missions.values() if m.status == "pending"
            ),
            "completed_count": sum(
                1 for m in self._missions.values() if m.status == "completed"
            ),
            "failed_count": sum(
                1 for m in self._missions.values() if m.status == "failed"
            ),
            "cancelled_count": sum(
                1 for m in self._missions.values() if m.status == "cancelled"
            ),
        }
