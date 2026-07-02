import math
from typing import Dict, Any, List, Optional
from app.optimizer.base import PipelineRunMetadata

class RollingStats:
    def __init__(self) -> None:
        self.values: List[float] = []

    def add(self, value: float) -> None:
        self.values.append(value)

    def _stats(self, subset: List[float]) -> dict:
        if not subset:
            return {"mean": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0, "std_dev": 0.0}
        
        sorted_val = sorted(subset)
        n = len(sorted_val)
        mean_val = sum(sorted_val) / n
        
        # median
        if n % 2 == 1:
            median_val = sorted_val[n // 2]
        else:
            median_val = (sorted_val[n // 2 - 1] + sorted_val[n // 2]) / 2.0
            
        # percentiles
        p95_idx = max(0, min(n - 1, int(math.ceil(0.95 * n) - 1)))
        p99_idx = max(0, min(n - 1, int(math.ceil(0.99 * n) - 1)))
        p95_val = sorted_val[p95_idx]
        p99_val = sorted_val[p99_idx]
        
        # standard deviation
        variance = sum((x - mean_val) ** 2 for x in sorted_val) / n
        std_dev = math.sqrt(variance)
        
        return {
            "mean": mean_val,
            "median": median_val,
            "p95": p95_val,
            "p99": p99_val,
            "std_dev": std_dev,
        }

    def get_metrics(self) -> dict:
        n = len(self.values)
        return {
            "last_100": self._stats(self.values[-100:] if n >= 100 else self.values),
            "last_1000": self._stats(self.values[-1000:] if n >= 1000 else self.values),
            "overall": self._stats(self.values),
        }


class PipelineStatisticsTracker:
    def __init__(self) -> None:
        self.total_latency = RollingStats()
        self.stage_latencies: Dict[str, RollingStats] = {}
        self.extractor_latencies: Dict[str, RollingStats] = {}
        self.cache_hit_ratio = RollingStats()
        self.token_utilization = RollingStats()
        self.context_reuse_ratio = RollingStats()
        self.incremental_update_ratio = RollingStats()
        
        self.failures_count = 0
        self.cancellations_count = 0
        self.timeouts_count = 0
        self.total_runs_count = 0

    def record_run(self, run: PipelineRunMetadata) -> None:
        self.total_runs_count += 1
        
        if run.status == "failed":
            self.failures_count += 1
        elif run.status == "cancelled":
            self.cancellations_count += 1
            
        if run.is_timeout:
            self.timeouts_count += 1
            
        self.total_latency.add(run.total_latency_ms)
        self.cache_hit_ratio.add(run.cache_hit_ratio)
        self.token_utilization.add(run.token_utilization)
        self.context_reuse_ratio.add(run.context_reuse_ratio)
        self.incremental_update_ratio.add(run.incremental_update_ratio)
        
        for stage, latency in run.stage_latencies.items():
            if stage not in self.stage_latencies:
                self.stage_latencies[stage] = RollingStats()
            self.stage_latencies[stage].add(latency)
            
        for ext, latency in run.extractor_latencies.items():
            if ext not in self.extractor_latencies:
                self.extractor_latencies[ext] = RollingStats()
            self.extractor_latencies[ext].add(latency)

    def get_summary(self) -> dict:
        return {
            "total_runs": self.total_runs_count,
            "failures": self.failures_count,
            "cancellations": self.cancellations_count,
            "timeouts": self.timeouts_count,
            "total_latency": self.total_latency.get_metrics(),
            "cache_hit_ratio": self.cache_hit_ratio.get_metrics(),
            "token_utilization": self.token_utilization.get_metrics(),
            "context_reuse_ratio": self.context_reuse_ratio.get_metrics(),
            "incremental_update_ratio": self.incremental_update_ratio.get_metrics(),
            "stages": {stage: stats.get_metrics() for stage, stats in self.stage_latencies.items()},
            "extractors": {ext: stats.get_metrics() for ext, stats in self.extractor_latencies.items()},
        }
