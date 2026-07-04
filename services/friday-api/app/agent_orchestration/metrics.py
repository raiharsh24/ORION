import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from app.optimizer.statistics import RollingStats


@dataclass
class AgentUtilizationRecord:
    agent_id: str
    role: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_ms: float = 0.0
    last_active: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return round(self.tasks_completed / total, 3) if total > 0 else 1.0


@dataclass
class DelegationRecord:
    mission_id: str
    agent_id: str
    capability: str
    success: bool
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


class AgentMissionMetrics:
    def __init__(self) -> None:
        self._agent_utilization: Dict[str, AgentUtilizationRecord] = {}
        self._delegation_history: List[DelegationRecord] = []
        self._parallel_execution_times = RollingStats()
        self._delegation_latencies = RollingStats()
        self._total_parallel_runs = 0
        self._time_saved_by_parallel_ms: float = 0.0

    def record_agent_task(self, agent_id: str, role: str,
                          success: bool, duration_ms: float) -> None:
        if agent_id not in self._agent_utilization:
            self._agent_utilization[agent_id] = AgentUtilizationRecord(
                agent_id=agent_id, role=role,
            )
        record = self._agent_utilization[agent_id]
        if success:
            record.tasks_completed += 1
        else:
            record.tasks_failed += 1
        record.total_execution_ms += duration_ms
        record.last_active = time.time()

    def record_delegation(self, mission_id: str, agent_id: str,
                          capability: str, success: bool,
                          duration_ms: float) -> None:
        self._delegation_history.append(DelegationRecord(
            mission_id=mission_id,
            agent_id=agent_id,
            capability=capability,
            success=success,
            duration_ms=duration_ms,
        ))
        self._delegation_latencies.add(duration_ms)

    def record_parallel_run(self, sequential_ms: float,
                            parallel_ms: float) -> None:
        self._total_parallel_runs += 1
        self._parallel_execution_times.add(parallel_ms)
        saved = sequential_ms - parallel_ms
        if saved > 0:
            self._time_saved_by_parallel_ms += saved

    def get_agent_utilization(self) -> Dict[str, Dict[str, Any]]:
        return {
            aid: {
                "role": rec.role,
                "tasks_completed": rec.tasks_completed,
                "tasks_failed": rec.tasks_failed,
                "success_rate": rec.success_rate,
                "total_execution_ms": rec.total_execution_ms,
                "last_active": rec.last_active,
            }
            for aid, rec in self._agent_utilization.items()
        }

    def get_delegation_summary(self) -> Dict[str, Any]:
        total = len(self._delegation_history)
        successful = sum(1 for d in self._delegation_history if d.success)
        return {
            "total_delegations": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(successful / total, 3) if total > 0 else 1.0,
            "latency": self._delegation_latencies.get_metrics(),
            "by_capability": self._get_delegation_by_capability(),
        }

    def _get_delegation_by_capability(self) -> Dict[str, Dict[str, Any]]:
        by_cap: Dict[str, Dict[str, Any]] = {}
        for d in self._delegation_history:
            if d.capability not in by_cap:
                by_cap[d.capability] = {"total": 0, "successful": 0, "failed": 0}
            by_cap[d.capability]["total"] += 1
            if d.success:
                by_cap[d.capability]["successful"] += 1
            else:
                by_cap[d.capability]["failed"] += 1
        return by_cap

    def get_parallel_summary(self) -> Dict[str, Any]:
        return {
            "total_parallel_runs": self._total_parallel_runs,
            "time_saved_ms": round(self._time_saved_by_parallel_ms, 2),
            "execution_times": self._parallel_execution_times.get_metrics(),
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "utilization": self.get_agent_utilization(),
            "delegation": self.get_delegation_summary(),
            "parallel": self.get_parallel_summary(),
        }
