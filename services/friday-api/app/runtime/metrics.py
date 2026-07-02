import time
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class RuntimeMetricsSnapshot:
    total_missions: int = 0
    active_missions: int = 0
    completed_missions: int = 0
    failed_missions: int = 0
    success_rate: float = 1.0
    average_duration_ms: float = 0.0
    average_planning_latency_ms: float = 0.0
    average_execution_latency_ms: float = 0.0
    total_retries: int = 0
    total_recoveries: int = 0
    agent_utilization: Dict[str, float] = field(default_factory=dict)
    failure_causes: Dict[str, int] = field(default_factory=dict)
    stage_latencies: Dict[str, float] = field(default_factory=dict)


class RuntimeMetrics:
    def __init__(self):
        self.reset()

    def record_mission_created(self) -> None:
        self._total += 1
        self._active += 1

    def record_mission_completed(self) -> None:
        self._completed += 1
        self._active = max(0, self._active - 1)

    def record_mission_failed(self) -> None:
        self._failed += 1
        self._active = max(0, self._active - 1)

    def record_duration(self, ms: float) -> None:
        self._durations.append(ms)

    def record_planning_latency(self, ms: float) -> None:
        self._planning_latencies.append(ms)

    def record_execution_latency(self, ms: float) -> None:
        self._execution_latencies.append(ms)

    def record_retry(self) -> None:
        self._retries += 1

    def record_recovery(self) -> None:
        self._recoveries += 1

    def record_agent_utilization(self, agent: str, fraction: float) -> None:
        self._agent_util[agent] = fraction

    def record_failure_cause(self, cause: str) -> None:
        self._failure_causes[cause] = self._failure_causes.get(cause, 0) + 1

    def record_stage_latency(self, stage: str, ms: float) -> None:
        if stage not in self._stage_latencies:
            self._stage_latencies[stage] = []
        self._stage_latencies[stage].append(ms)

    def snapshot(self) -> RuntimeMetricsSnapshot:
        def avg(vals: List[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        avg_stage: Dict[str, float] = {}
        for stage, vals in self._stage_latencies.items():
            avg_stage[stage] = round(avg(vals), 2)

        total = self._total if self._total > 0 else 1
        return RuntimeMetricsSnapshot(
            total_missions=self._total,
            active_missions=self._active,
            completed_missions=self._completed,
            failed_missions=self._failed,
            success_rate=round(self._completed / total, 3),
            average_duration_ms=round(avg(self._durations), 2),
            average_planning_latency_ms=round(avg(self._planning_latencies), 2),
            average_execution_latency_ms=round(avg(self._execution_latencies), 2),
            total_retries=self._retries,
            total_recoveries=self._recoveries,
            agent_utilization=dict(self._agent_util),
            failure_causes=dict(self._failure_causes),
            stage_latencies=avg_stage,
        )

    def reset(self) -> None:
        self._total = 0
        self._active = 0
        self._completed = 0
        self._failed = 0
        self._durations: List[float] = []
        self._planning_latencies: List[float] = []
        self._execution_latencies: List[float] = []
        self._retries = 0
        self._recoveries = 0
        self._agent_util: Dict[str, float] = {}
        self._failure_causes: Dict[str, int] = {}
        self._stage_latencies: Dict[str, List[float]] = {}
