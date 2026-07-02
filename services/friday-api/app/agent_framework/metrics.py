import time
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class MetricsSnapshot:
    delegation_count: int = 0
    total_parallel_runs: int = 0
    average_parallel_efficiency: float = 0.0
    average_queue_latency_ms: float = 0.0
    agent_utilization: Dict[str, float] = field(default_factory=dict)
    overall_utilization: float = 0.0
    idle_percentage: float = 100.0
    recovery_count: int = 0
    total_tasks_completed: int = 0


class MetricsCollector:
    def __init__(self):
        self._delegation_count = 0
        self._parallel_runs: List[Dict[str, Any]] = []
        self._queue_latencies: List[float] = []
        self._agent_busy_time: Dict[str, float] = {}
        self._agent_total_time: Dict[str, float] = {}
        self._recovery_count = 0
        self._tasks_completed = 0
        self._start_time = time.time()

    @property
    def delegation_count(self) -> int:
        return self._delegation_count

    @property
    def tasks_completed(self) -> int:
        return self._tasks_completed

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    def record_delegation(self) -> None:
        self._delegation_count += 1

    def record_parallel_run(self, agents_used: int,
                            total_agents: int) -> None:
        efficiency = agents_used / total_agents if total_agents > 0 else 0
        self._parallel_runs.append({
            "agents_used": agents_used,
            "total_agents": total_agents,
            "efficiency": efficiency,
            "timestamp": time.time(),
        })

    def record_queue_latency(self, wait_time_ms: float) -> None:
        self._queue_latencies.append(wait_time_ms)

    def record_utilization(self, agent_id: str, busy_seconds: float,
                           total_seconds: float) -> None:
        self._agent_busy_time[agent_id] = (
            self._agent_busy_time.get(agent_id, 0) + busy_seconds
        )
        self._agent_total_time[agent_id] = (
            self._agent_total_time.get(agent_id, 0) + total_seconds
        )

    def record_recovery(self) -> None:
        self._recovery_count += 1

    def record_task_completed(self) -> None:
        self._tasks_completed += 1

    def snapshot(self) -> MetricsSnapshot:
        total_busy = sum(self._agent_busy_time.values())
        total_all = sum(self._agent_total_time.values())
        if total_all == 0:
            total_all = 1
        overall_util = total_busy / total_all

        agent_util: Dict[str, float] = {}
        for agent_id in self._agent_busy_time:
            total_t = self._agent_total_time.get(agent_id, 1)
            agent_util[agent_id] = (
                self._agent_busy_time[agent_id] / total_t if total_t > 0 else 0
            )

        avg_efficiency = 0.0
        if self._parallel_runs:
            avg_efficiency = (
                sum(r["efficiency"] for r in self._parallel_runs)
                / len(self._parallel_runs)
            )

        avg_latency = 0.0
        if self._queue_latencies:
            avg_latency = (
                sum(self._queue_latencies) / len(self._queue_latencies)
            )

        return MetricsSnapshot(
            delegation_count=self._delegation_count,
            total_parallel_runs=len(self._parallel_runs),
            average_parallel_efficiency=round(avg_efficiency, 3),
            average_queue_latency_ms=round(avg_latency, 2),
            agent_utilization={k: round(v, 3) for k, v in agent_util.items()},
            overall_utilization=round(overall_util, 3),
            idle_percentage=round((1 - overall_util) * 100, 1),
            recovery_count=self._recovery_count,
            total_tasks_completed=self._tasks_completed,
        )

    def get_data(self) -> Dict[str, Any]:
        return {
            "delegation_count": self._delegation_count,
            "recovery_count": self._recovery_count,
            "tasks_completed": self._tasks_completed,
        }

    def reset(self) -> None:
        self.__init__()
