import uuid
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DelegationTask:
    task_id: str
    agent_id: str
    task_type: str
    payload: Dict[str, Any]
    status: str = "pending"
    parent_task_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = 0.0
    completed_at: Optional[float] = None


@dataclass
class DelegationHealth:
    status: str = "healthy"
    total_tasks: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0


class DelegationManager:
    def __init__(self):
        self._tasks: Dict[str, DelegationTask] = {}
        self._completion_callbacks: List[callable] = []

    def on_completion(self, callback: callable) -> None:
        self._completion_callbacks.append(callback)

    async def delegate(self, parent_task_id: Optional[str], agent_id: str,
                       task_type: str, payload: Dict[str, Any],
                       dependencies: Optional[List[str]] = None) -> DelegationTask:
        task_id = str(uuid.uuid4())
        task = DelegationTask(
            task_id=task_id,
            agent_id=agent_id,
            task_type=task_type,
            payload=payload,
            parent_task_id=parent_task_id,
            dependencies=dependencies or [],
            created_at=time.time(),
        )
        self._tasks[task_id] = task
        if parent_task_id and parent_task_id in self._tasks:
            parent = self._tasks[parent_task_id]
            if task_id not in parent.children:
                parent.children.append(task_id)
        return task

    async def complete_task(self, task_id: str, result: Any) -> Optional[DelegationTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        old_status = task.status
        task.status = "completed"
        task.result = result
        task.completed_at = time.time()
        ready = self._check_ready_children(task_id)
        for cb in self._completion_callbacks:
            try:
                cb(task, old_status, "completed")
            except Exception:
                pass
        return task

    async def fail_task(self, task_id: str, error: str) -> Optional[DelegationTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        old_status = task.status
        task.status = "failed"
        task.error = error
        for cb in self._completion_callbacks:
            try:
                cb(task, old_status, "failed")
            except Exception:
                pass
        return task

    async def set_running(self, task_id: str) -> Optional[DelegationTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = "running"
        return task

    def get_task(self, task_id: str) -> Optional[DelegationTask]:
        return self._tasks.get(task_id)

    def get_subtasks(self, parent_task_id: str) -> List[DelegationTask]:
        return [t for t in self._tasks.values()
                if t.parent_task_id == parent_task_id]

    def get_children(self, task_id: str) -> List[DelegationTask]:
        parent = self._tasks.get(task_id)
        if not parent:
            return []
        return [self._tasks[cid] for cid in parent.children if cid in self._tasks]

    def get_dependency_graph(self, task_id: str) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        for tid, t in self._tasks.items():
            graph[tid] = list(t.dependencies)
        return graph

    def get_pending_tasks(self, agent_id: Optional[str] = None) -> List[DelegationTask]:
        tasks = [t for t in self._tasks.values() if t.status == "pending"]
        if agent_id:
            tasks = [t for t in tasks if t.agent_id == agent_id]
        return tasks

    def get_ready_tasks(self) -> List[DelegationTask]:
        ready = []
        for t in self._tasks.values():
            if t.status == "pending":
                deps_met = all(
                    self._tasks.get(d) and self._tasks[d].status == "completed"
                    for d in t.dependencies
                )
                if deps_met:
                    ready.append(t)
        return ready

    def get_all_active(self) -> List[DelegationTask]:
        return [t for t in self._tasks.values()
                if t.status in ("pending", "running")]

    def get_all(self) -> List[DelegationTask]:
        return list(self._tasks.values())

    def count(self) -> int:
        return len(self._tasks)

    def count_by_status(self, status: str) -> int:
        return sum(1 for t in self._tasks.values() if t.status == status)

    def restore_task(self, task_data: Dict[str, Any]) -> Optional[DelegationTask]:
        task_id = task_data.get("task_id", str(uuid.uuid4()))
        task = DelegationTask(
            task_id=task_id,
            agent_id=task_data.get("agent_id", ""),
            task_type=task_data.get("task_type", ""),
            payload=task_data.get("payload", {}),
            status=task_data.get("status", "pending"),
            parent_task_id=task_data.get("parent_task_id"),
            dependencies=task_data.get("dependencies", []),
            children=task_data.get("children", []),
            result=task_data.get("result"),
            error=task_data.get("error"),
            created_at=task_data.get("created_at", time.time()),
            completed_at=task_data.get("completed_at"),
        )
        self._tasks[task_id] = task
        return task

    def _check_ready_children(self, completed_task_id: str) -> List[str]:
        ready: List[str] = []
        for tid, t in self._tasks.items():
            if t.status == "pending" and completed_task_id in t.dependencies:
                deps_met = all(
                    self._tasks.get(d) and self._tasks[d].status == "completed"
                    for d in t.dependencies
                )
                if deps_met:
                    ready.append(tid)
        return ready

    def health(self) -> DelegationHealth:
        return DelegationHealth(
            status="healthy",
            total_tasks=self.count(),
            pending=self.count_by_status("pending"),
            running=self.count_by_status("running"),
            completed=self.count_by_status("completed"),
            failed=self.count_by_status("failed"),
        )
