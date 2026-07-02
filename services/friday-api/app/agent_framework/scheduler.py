import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta


@dataclass
class ScheduleEntry:
    entry_id: str
    agent_id: str
    task_type: str
    payload: Dict[str, Any]
    interval_seconds: float = 0.0
    max_runs: int = 0
    run_count: int = 0
    next_run: Optional[datetime] = None
    created_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    status: str = "pending"


class AgentScheduler:
    def __init__(self):
        self._entries: Dict[str, ScheduleEntry] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._handlers: Dict[str, Callable] = {}
        self._tick_interval = 0.1

    def register_handler(self, task_type: str,
                         handler: Callable[[ScheduleEntry], Awaitable[None]]) -> None:
        self._handlers[task_type] = handler

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._tick_loop())

    async def shutdown(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):
                pass
            self._loop_task = None
        for tid, task in self._background_tasks.items():
            task.cancel()
        self._background_tasks.clear()

    def schedule(self, agent_id: str, task_type: str,
                 payload: Dict[str, Any],
                 delay_seconds: float = 0.0,
                 interval_seconds: float = 0.0,
                 max_runs: int = 0) -> str:
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(seconds=delay_seconds) if delay_seconds > 0 else now
        entry = ScheduleEntry(
            entry_id=entry_id,
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
            interval_seconds=interval_seconds,
            max_runs=max_runs,
            next_run=next_run,
            created_at=now,
            status="pending",
        )
        self._entries[entry_id] = entry
        return entry_id

    def cancel(self, entry_id: str) -> bool:
        entry = self._entries.pop(entry_id, None)
        if entry is None:
            return False
        bg = self._background_tasks.pop(entry_id, None)
        if bg:
            bg.cancel()
        return True

    def get(self, entry_id: str) -> Optional[ScheduleEntry]:
        return self._entries.get(entry_id)

    def list_entries(self) -> List[ScheduleEntry]:
        return list(self._entries.values())

    def list_by_agent(self, agent_id: str) -> List[ScheduleEntry]:
        return [e for e in self._entries.values() if e.agent_id == agent_id]

    async def _tick_loop(self) -> None:
        while self._running:
            now = datetime.now(timezone.utc)
            due = [
                e for e in self._entries.values()
                if e.next_run and e.next_run <= now and e.status == "pending"
            ]
            for entry in due:
                if entry.max_runs > 0 and entry.run_count >= entry.max_runs:
                    entry.status = "completed"
                    continue
                handler = self._handlers.get(entry.task_type)
                if handler:
                    task = asyncio.create_task(self._execute_entry(entry, handler))
                    self._background_tasks[entry.entry_id] = task
                entry.run_count += 1
                entry.last_run = now
                if entry.interval_seconds > 0:
                    entry.next_run = now + timedelta(seconds=entry.interval_seconds)
                else:
                    entry.status = "completed"
            await asyncio.sleep(self._tick_interval)

    async def _execute_entry(self, entry: ScheduleEntry,
                              handler: Callable) -> None:
        try:
            await handler(entry)
        except Exception:
            pass
        finally:
            self._background_tasks.pop(entry.entry_id, None)

    def health(self) -> dict:
        return {
            "scheduled_entries": len(self._entries),
            "active_tasks": len(self._background_tasks),
            "running": self._running,
            "handlers": list(self._handlers.keys()),
        }
