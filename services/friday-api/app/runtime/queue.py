import asyncio
import heapq
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable


class MissionPriority:
    LOW = 0
    MEDIUM = 5
    HIGH = 10
    CRITICAL = 20


@dataclass(order=True)
class QueueEntry:
    priority: int
    enqueued_at: float
    entry_id: str = field(compare=False)
    mission_id: str = field(compare=False)
    dependency_ids: List[str] = field(default_factory=list, compare=False)
    timeout_s: float = field(default=300.0, compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass
class QueueStatus:
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    max_concurrent: int
    active_entries: List[str]


class MissionQueue:
    def __init__(self, max_concurrent: int = 4):
        self._heap: List[QueueEntry] = []
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._running: Dict[str, asyncio.Task] = {}
        self._completed: set = set()
        self._failed: Dict[str, str] = {}
        self._cancelled: set = set()
        self._handler: Optional[Callable] = None
        self._completion_hooks: List[Callable] = []
        self._processing = False

    def set_handler(self, handler: Callable) -> None:
        self._handler = handler

    def on_completion(self, hook: Callable) -> None:
        self._completion_hooks.append(hook)

    async def enqueue(self, mission_id: str, priority: int = MissionPriority.MEDIUM,
                      dependency_ids: Optional[List[str]] = None,
                      timeout_s: float = 300.0) -> str:
        entry_id = str(uuid.uuid4())
        entry = QueueEntry(
            priority=-priority,
            enqueued_at=time.time(),
            entry_id=entry_id,
            mission_id=mission_id,
            dependency_ids=dependency_ids or [],
            timeout_s=timeout_s,
        )
        async with self._lock:
            heapq.heappush(self._heap, entry)
        return entry_id

    async def _process_queue(self) -> None:
        if self._processing:
            return
        self._processing = True
        try:
            while True:
                entry = await self._find_next_ready()
                if entry is None:
                    break
                asyncio.create_task(self._execute_entry(entry))
                await asyncio.sleep(0)
        finally:
            self._processing = False

    async def _find_next_ready(self) -> Optional[QueueEntry]:
        async with self._lock:
            if not self._heap:
                return None
            scanned: List[QueueEntry] = []
            found = None
            while self._heap and found is None:
                entry = heapq.heappop(self._heap)
                deps = entry.dependency_ids
                dep_met = all(d in self._completed for d in deps)
                if dep_met and entry.mission_id not in self._cancelled:
                    found = entry
                else:
                    scanned.append(entry)
            for e in scanned:
                heapq.heappush(self._heap, e)
            return found

    def start_processing(self) -> None:
        asyncio.create_task(self._process_queue())

    async def _execute_entry(self, entry: QueueEntry) -> None:
        async with self._semaphore:
            if entry.mission_id in self._cancelled:
                self._cancelled.discard(entry.mission_id)
                return
            if not self._handler:
                self._completed.add(entry.mission_id)
                return

            task = asyncio.create_task(self._handler(entry.mission_id))
            self._running[entry.mission_id] = task
            try:
                result = await asyncio.wait_for(task, timeout=entry.timeout_s)
                self._completed.add(entry.mission_id)
                for hook in self._completion_hooks:
                    try:
                        hook(entry.mission_id, result, None)
                    except Exception:
                        pass
            except asyncio.TimeoutError:
                self._failed[entry.mission_id] = "timeout"
                for hook in self._completion_hooks:
                    try:
                        hook(entry.mission_id, None, "timeout")
                    except Exception:
                        pass
            except Exception as e:
                self._failed[entry.mission_id] = str(e)
                for hook in self._completion_hooks:
                    try:
                        hook(entry.mission_id, None, str(e))
                    except Exception:
                        pass
            finally:
                self._running.pop(entry.mission_id, None)

        asyncio.create_task(self._process_queue())

    async def cancel(self, mission_id: str) -> bool:
        self._cancelled.add(mission_id)
        in_heap = False
        async with self._lock:
            old_len = len(self._heap)
            self._heap = [e for e in self._heap if e.mission_id != mission_id]
            heapq.heapify(self._heap)
            in_heap = len(self._heap) < old_len

        task = self._running.get(mission_id)
        if task and not task.done():
            task.cancel()
            self._running.pop(mission_id, None)
            return True

        if in_heap:
            return True

        return mission_id in self._completed or mission_id in self._failed

    async def retry(self, mission_id: str) -> bool:
        if mission_id in self._failed:
            self._failed.pop(mission_id)
            await self.enqueue(mission_id)
            return True
        return False

    def peek(self) -> Optional[QueueEntry]:
        if not self._heap:
            return None
        return self._heap[0]

    def is_running(self, mission_id: str) -> bool:
        return mission_id in self._running

    def is_completed(self, mission_id: str) -> bool:
        return mission_id in self._completed

    def is_failed(self, mission_id: str) -> bool:
        return mission_id in self._failed

    def is_cancelled(self, mission_id: str) -> bool:
        return mission_id in self._cancelled

    def list_queued(self) -> List[str]:
        return [e.mission_id for e in self._heap]

    def list_running(self) -> List[str]:
        return list(self._running.keys())

    async def wait_for_all(self) -> None:
        self.start_processing()
        while self._heap or self._running:
            await asyncio.sleep(0.1)

    @property
    def status(self) -> QueueStatus:
        return QueueStatus(
            queued=len(self._heap),
            running=len(self._running),
            completed=len(self._completed),
            failed=len(self._failed),
            cancelled=len(self._cancelled),
            max_concurrent=self._max_concurrent,
            active_entries=[*self.list_queued(), *self.list_running()],
        )

    @property
    def size(self) -> int:
        return len(self._heap)

    def stop_processing(self) -> None:
        """Cancel all running tasks and clear the queue."""
        for mission_id, task in list(self._running.items()):
            if not task.done():
                task.cancel()
            self._running.pop(mission_id, None)
        self._heap.clear()
        self._processing = False

    def clear(self) -> None:
        self._heap.clear()
        self._completed.clear()
        self._failed.clear()
        self._cancelled.clear()
