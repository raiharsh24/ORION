import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class MissionTelemetry:
    mission_id: str
    intent: str = ""
    total_duration_ms: float = 0.0
    planning_latency_ms: float = 0.0
    resolution_latency_ms: float = 0.0
    execution_latency_ms: float = 0.0
    reflection_latency_ms: float = 0.0
    tool_latencies: Dict[str, float] = field(default_factory=dict)
    agent_utilization: Dict[str, float] = field(default_factory=dict)
    retry_count: int = 0
    recovery_count: int = 0
    stage_timings: Dict[str, float] = field(default_factory=dict)
    success: bool = True
    failure_stage: str = ""
    failure_reason: str = ""


class TelemetryCollector:
    def __init__(self):
        self._missions: Dict[str, MissionTelemetry] = {}
        self._counters: Dict[str, int] = {
            "total": 0, "success": 0, "failed": 0,
            "total_retries": 0, "total_recoveries": 0,
        }
        self._latency_history: List[float] = []
        self._failure_causes: Dict[str, int] = {}

    def create_mission(self, mission_id: str, intent: str = "") -> MissionTelemetry:
        t = MissionTelemetry(mission_id=mission_id, intent=intent)
        self._missions[mission_id] = t
        self._counters["total"] += 1
        return t

    def record_planning_latency(self, mission_id: str, ms: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.planning_latency_ms = ms
        self._latency_history.append(ms)

    def record_resolution_latency(self, mission_id: str, ms: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.resolution_latency_ms = ms

    def record_execution_latency(self, mission_id: str, ms: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.execution_latency_ms = ms

    def record_reflection_latency(self, mission_id: str, ms: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.reflection_latency_ms = ms

    def record_tool_latency(self, mission_id: str, tool: str, ms: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.tool_latencies[tool] = ms

    def record_agent_utilization(self, mission_id: str, agent: str,
                                  fraction: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.agent_utilization[agent] = fraction

    def record_retry(self, mission_id: str) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.retry_count += 1
        self._counters["total_retries"] += 1

    def record_recovery(self, mission_id: str) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.recovery_count += 1
        self._counters["total_recoveries"] += 1

    def record_completion(self, mission_id: str, success: bool,
                           total_duration_ms: float = 0.0) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.success = success
            t.total_duration_ms = total_duration_ms
        if success:
            self._counters["success"] += 1
        else:
            self._counters["failed"] += 1

    def record_failure(self, mission_id: str, stage: str,
                        reason: str) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.failure_stage = stage
            t.failure_reason = reason
        self._failure_causes[reason] = self._failure_causes.get(reason, 0) + 1

    def record_stage_timing(self, mission_id: str, stage: str,
                             ms: float) -> None:
        t = self._missions.get(mission_id)
        if t:
            t.stage_timings[stage] = ms

    def get_mission(self, mission_id: str) -> Optional[MissionTelemetry]:
        return self._missions.get(mission_id)

    @property
    def total_missions(self) -> int:
        return self._counters["total"]

    @property
    def success_rate(self) -> float:
        total = self._counters["total"]
        if total == 0:
            return 1.0
        return self._counters["success"] / total

    @property
    def average_latency_ms(self) -> float:
        if not self._latency_history:
            return 0.0
        return sum(self._latency_history) / len(self._latency_history)

    @property
    def failure_causes(self) -> Dict[str, int]:
        return dict(self._failure_causes)

    @property
    def total_retries(self) -> int:
        return self._counters["total_retries"]

    @property
    def total_recoveries(self) -> int:
        return self._counters["total_recoveries"]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "total_missions": self._counters["total"],
            "successful": self._counters["success"],
            "failed": self._counters["failed"],
            "success_rate": round(self.success_rate, 3),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "total_retries": self._counters["total_retries"],
            "total_recoveries": self._counters["total_recoveries"],
            "failure_causes": dict(self._failure_causes),
        }

    def reset(self) -> None:
        self._missions.clear()
        self._counters = {"total": 0, "success": 0, "failed": 0,
                          "total_retries": 0, "total_recoveries": 0}
        self._latency_history.clear()
        self._failure_causes.clear()

