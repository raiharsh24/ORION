import asyncio
import time
import heapq
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

from app.agent_framework.delegation import DelegationManager
from app.agent_framework.blackboard import Blackboard
from app.agent_framework.priority import PriorityEngine


@dataclass
class CoordinatorHealth:
    status: str = "healthy"
    queue_size: int = 0
    active_tasks: int = 0
    resources_allocated: int = 0


class Coordinator:
    def __init__(self, agent_manager: Any,
                 delegation_manager: Optional[DelegationManager] = None,
                 blackboard: Optional[Blackboard] = None,
                 priority_engine: Optional[PriorityEngine] = None,
                 metrics: Optional[Any] = None):
        self._agent_manager = agent_manager
        self._delegation = delegation_manager
        self._blackboard = blackboard
        self._priority_engine = priority_engine or PriorityEngine()
        self._metrics = metrics
        self._queue: List[tuple] = []
        self._queue_lock = asyncio.Lock()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._allocated_resources: Dict[str, Dict[str, int]] = {}
        self._execute_hooks: List[Callable] = []

    def on_execute(self, hook: Callable) -> None:
        self._execute_hooks.append(hook)

    async def execute_serial(self, tasks: List[Dict[str, Any]]) -> List[Any]:
        results = []
        for task_info in tasks:
            result = await self._execute_single(task_info)
            results.append(result)
        return results

    async def execute_parallel(self, tasks: List[Dict[str, Any]]) -> List[Any]:
        coros = [self._execute_single(t) for t in tasks]
        gathered = await asyncio.gather(*coros, return_exceptions=True)
        return [r for r in gathered if not isinstance(r, Exception)]

    async def execute_dependency_aware(
        self, task_graph: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        executed: set = set()
        results: Dict[str, Any] = {}

        while len(executed) < len(task_graph):
            batch = []
            batch_ids = []
            for task_id, info in task_graph.items():
                if task_id in executed:
                    continue
                deps = info.get("depends_on", [])
                if all(d in executed for d in deps):
                    batch.append(info)
                    batch_ids.append(task_id)
                    executed.add(task_id)
            if not batch:
                break
            batch_results = await self.execute_parallel(batch)
            for i, task_id in enumerate(batch_ids):
                results[task_id] = batch_results[i] if i < len(batch_results) else None
        return results

    async def enqueue(self, task_info: Dict[str, Any], priority: float = 5.0) -> None:
        async with self._queue_lock:
            heapq.heappush(self._queue, (-priority, time.time(), task_info))

    async def process_queue(self, max_tasks: int = 1) -> List[Any]:
        async with self._queue_lock:
            tasks = []
            for _ in range(min(max_tasks, len(self._queue))):
                _, _, task = heapq.heappop(self._queue)
                tasks.append(task)
        if not tasks:
            return []
        return await self.execute_parallel(tasks)

    async def enqueue_and_wait(self, task_info: Dict[str, Any],
                               priority: float = 5.0) -> Any:
        await self.enqueue(task_info, priority)
        results = await self.process_queue(1)
        return results[0] if results else None

    async def allocate_resource(self, agent_id: str, resource: str,
                                quantity: int = 1) -> bool:
        if agent_id not in self._allocated_resources:
            self._allocated_resources[agent_id] = {}
        self._allocated_resources[agent_id][resource] = (
            self._allocated_resources[agent_id].get(resource, 0) + quantity
        )
        return True

    async def release_resource(self, agent_id: str, resource: str,
                               quantity: int = 1) -> bool:
        if agent_id in self._allocated_resources:
            current = self._allocated_resources[agent_id].get(resource, 0)
            self._allocated_resources[agent_id][resource] = max(0, current - quantity)
            if self._allocated_resources[agent_id][resource] == 0:
                del self._allocated_resources[agent_id][resource]
        return True

    def get_allocated_resources(self, agent_id: Optional[str] = None) -> Dict:
        if agent_id:
            return self._allocated_resources.get(agent_id, {})
        return dict(self._allocated_resources)

    def get_queue_length(self) -> int:
        return len(self._queue)

    def get_active_count(self) -> int:
        return len(self._active_tasks)

    async def _execute_single(self, task_info: Dict[str, Any]) -> Optional[Any]:
        agent_id = task_info.get("agent_id", "")
        task_type = task_info.get("type", task_info.get("task_type", ""))
        payload = task_info.get("payload", {})

        if self._metrics:
            self._metrics.record_task_completed()

        for hook in self._execute_hooks:
            try:
                hook(task_info)
            except Exception:
                pass

        return await self._agent_manager.execute_task(agent_id, task_type, payload)

    def health(self) -> CoordinatorHealth:
        return CoordinatorHealth(
            status="healthy",
            queue_size=self.get_queue_length(),
            active_tasks=self.get_active_count(),
            resources_allocated=sum(
                len(v) for v in self._allocated_resources.values()
            ),
        )
