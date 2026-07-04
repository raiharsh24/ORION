import math
from typing import Dict, Any, List, Optional
from loguru import logger

from app.optimizer.statistics import RollingStats


class MissionAnalytics:
    """Tracks mission-level analytics:

    - Average completion time
    - Success rate
    - Failure categories
    - Tool reliability
    - Planner accuracy
    - Recovery frequency

    Exposes data through the existing metrics infrastructure (RuntimeMetrics)
    and the optimizer's RollingStats statistical engine.
    """

    def __init__(self) -> None:
        self.completion_times = RollingStats()
        self.planner_latencies = RollingStats()
        self.execution_latencies = RollingStats()
        self.recovery_latencies = RollingStats()

        self._total_missions = 0
        self._successful = 0
        self._failed = 0
        self._cancelled = 0

        self._failure_categories: Dict[str, int] = {}
        self._tool_usage: Dict[str, Dict[str, int]] = {}
        self._recovery_frequency: Dict[str, int] = {}
        self._planner_accuracy: Dict[str, int] = {"correct": 0, "incorrect": 0}
        self._stage_latencies: Dict[str, List[float]] = {}

    def record_mission(
        self,
        mission_id: str,
        success: bool,
        duration_ms: float,
        failure_category: str = "",
        planner_latency_ms: float = 0.0,
        execution_latency_ms: float = 0.0,
    ) -> None:
        self._total_missions += 1
        if success:
            self._successful += 1
        else:
            self._failed += 1
            if failure_category:
                self._failure_categories[failure_category] = (
                    self._failure_categories.get(failure_category, 0) + 1
                )

        self.completion_times.add(duration_ms)
        if planner_latency_ms > 0:
            self.planner_latencies.add(planner_latency_ms)
        if execution_latency_ms > 0:
            self.execution_latencies.add(execution_latency_ms)

    def record_mission_cancelled(self) -> None:
        self._cancelled += 1

    def record_tool_usage(self, tool_name: str, success: bool) -> None:
        if tool_name not in self._tool_usage:
            self._tool_usage[tool_name] = {"success": 0, "fail": 0}
        if success:
            self._tool_usage[tool_name]["success"] += 1
        else:
            self._tool_usage[tool_name]["fail"] += 1

    def record_recovery(self, strategy: str, success: bool) -> None:
        self._recovery_frequency[strategy] = (
            self._recovery_frequency.get(strategy, 0) + 1
        )

    def record_planner_accuracy(self, correct: bool) -> None:
        if correct:
            self._planner_accuracy["correct"] += 1
        else:
            self._planner_accuracy["incorrect"] += 1

    def record_stage_latency(self, stage: str, ms: float) -> None:
        if stage not in self._stage_latencies:
            self._stage_latencies[stage] = []
        self._stage_latencies[stage].append(ms)

    @property
    def success_rate(self) -> float:
        total = self._total_missions
        return round(self._successful / total, 3) if total > 0 else 1.0

    @property
    def planner_accuracy_rate(self) -> float:
        total = self._planner_accuracy["correct"] + self._planner_accuracy["incorrect"]
        return round(self._planner_accuracy["correct"] / total, 3) if total > 0 else 1.0

    def get_tool_reliability(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for tool, counts in self._tool_usage.items():
            total = counts["success"] + counts["fail"]
            result[tool] = {
                "total_uses": total,
                "success_count": counts["success"],
                "fail_count": counts["fail"],
                "success_rate": round(counts["success"] / total, 3) if total > 0 else 0.0,
            }
        return result

    def get_failure_categories(self) -> Dict[str, int]:
        return dict(sorted(
            self._failure_categories.items(),
            key=lambda x: x[1],
            reverse=True,
        ))

    def get_stage_performance(self) -> Dict[str, Dict[str, float]]:
        result: Dict[str, Dict[str, float]] = {}
        for stage, latencies in self._stage_latencies.items():
            if latencies:
                result[stage] = {
                    "avg_ms": round(sum(latencies) / len(latencies), 2),
                    "count": len(latencies),
                    "min_ms": round(min(latencies), 2),
                    "max_ms": round(max(latencies), 2),
                }
        return result

    def get_summary(self) -> Dict[str, Any]:
        return {
            "missions": {
                "total": self._total_missions,
                "successful": self._successful,
                "failed": self._failed,
                "cancelled": self._cancelled,
                "success_rate": self.success_rate,
            },
            "completion_times": self.completion_times.get_metrics(),
            "planner_latencies": self.planner_latencies.get_metrics(),
            "execution_latencies": self.execution_latencies.get_metrics(),
            "failure_categories": self.get_failure_categories(),
            "tool_reliability": self.get_tool_reliability(),
            "planner_accuracy": {
                "correct": self._planner_accuracy["correct"],
                "incorrect": self._planner_accuracy["incorrect"],
                "accuracy_rate": self.planner_accuracy_rate,
            },
            "recovery_frequency": dict(self._recovery_frequency),
            "stage_performance": self.get_stage_performance(),
        }
