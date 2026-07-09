import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ExecutionMetrics:
    execution_count: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    stage_latencies: Dict[str, List[float]] = field(default_factory=dict)
    stage_errors: Dict[str, int] = field(default_factory=dict)
    failures: int = 0
    successes: int = 0
    cancellations: int = 0
    retries: int = 0

    def record_execution(self, duration_ms: float, success: bool) -> None:
        self.execution_count += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.execution_count
        if success:
            self.successes += 1
        else:
            self.failures += 1

    def record_stage(self, stage: str, duration_ms: float, error: Optional[str] = None) -> None:
        if stage not in self.stage_latencies:
            self.stage_latencies[stage] = []
        self.stage_latencies[stage].append(duration_ms)
        if error:
            self.stage_errors[stage] = self.stage_errors.get(stage, 0) + 1

    def record_cancellation(self) -> None:
        self.cancellations += 1

    def record_retry(self) -> None:
        self.retries += 1

    def snapshot(self) -> Dict[str, Any]:
        avg_stages = {}
        for stage, latencies in self.stage_latencies.items():
            avg_stages[stage] = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        return {
            "execution_count": self.execution_count,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "successes": self.successes,
            "failures": self.failures,
            "cancellations": self.cancellations,
            "retries": self.retries,
            "stage_average_latencies_ms": avg_stages,
            "stage_errors": dict(self.stage_errors),
        }

    def reset(self) -> None:
        self.execution_count = 0
        self.total_duration_ms = 0.0
        self.avg_duration_ms = 0.0
        self.stage_latencies.clear()
        self.stage_errors.clear()
        self.failures = 0
        self.successes = 0
        self.cancellations = 0
        self.retries = 0
