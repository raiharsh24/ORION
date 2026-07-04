import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RequestMetrics:
    count: int = 0
    total_latency_ms: float = 0.0
    errors: int = 0


@dataclass
class LatencyHistogram:
    buckets: Dict[str, int] = field(default_factory=lambda: {
        "<10ms": 0, "<50ms": 0, "<100ms": 0, "<500ms": 0,
        "<1s": 0, "<5s": 0, ">=5s": 0,
    })

    def record(self, latency_ms: float) -> None:
        if latency_ms < 10:
            self.buckets["<10ms"] += 1
        elif latency_ms < 50:
            self.buckets["<50ms"] += 1
        elif latency_ms < 100:
            self.buckets["<100ms"] += 1
        elif latency_ms < 500:
            self.buckets["<500ms"] += 1
        elif latency_ms < 1000:
            self.buckets["<1s"] += 1
        elif latency_ms < 5000:
            self.buckets["<5s"] += 1
        else:
            self.buckets[">=5s"] += 1


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, RequestMetrics] = defaultdict(RequestMetrics)
        self._latency: LatencyHistogram = LatencyHistogram()
        self._tool_executions: int = 0
        self._workflow_executions: int = 0
        self._missions_completed: int = 0
        self._missions_failed: int = 0
        self._model_calls: int = 0
        self._model_total_latency_ms: float = 0.0
        self._websocket_connections: int = 0
        self._websocket_peak: int = 0
        self._start_time: float = time.time()

    def record_request(self, endpoint: str, latency_ms: float, status: int) -> None:
        with self._lock:
            self._requests[endpoint].count += 1
            self._requests[endpoint].total_latency_ms += latency_ms
            if status >= 400:
                self._requests[endpoint].errors += 1
            self._latency.record(latency_ms)

    def record_tool_execution(self) -> None:
        with self._lock:
            self._tool_executions += 1

    def record_workflow_execution(self) -> None:
        with self._lock:
            self._workflow_executions += 1

    def record_mission_completed(self) -> None:
        with self._lock:
            self._missions_completed += 1

    def record_mission_failed(self) -> None:
        with self._lock:
            self._missions_failed += 1

    def record_model_call(self, latency_ms: float) -> None:
        with self._lock:
            self._model_calls += 1
            self._model_total_latency_ms += latency_ms

    def record_websocket_connect(self) -> None:
        with self._lock:
            self._websocket_connections += 1
            current = self._websocket_connections
            if current > self._websocket_peak:
                self._websocket_peak = current

    def record_websocket_disconnect(self) -> None:
        with self._lock:
            if self._websocket_connections > 0:
                self._websocket_connections -= 1

    def snapshot(self) -> Dict:
        with self._lock:
            uptime = time.time() - self._start_time
            total_requests = sum(r.count for r in self._requests.values())
            total_latency = sum(r.total_latency_ms for r in self._requests.values())
            total_errors = sum(r.errors for r in self._requests.values())

            per_endpoint = {}
            for ep, m in sorted(self._requests.items()):
                avg_latency = m.total_latency_ms / m.count if m.count > 0 else 0.0
                per_endpoint[ep] = {
                    "count": m.count,
                    "avg_latency_ms": round(avg_latency, 2),
                    "errors": m.errors,
                }

            model_avg = self._model_total_latency_ms / self._model_calls if self._model_calls > 0 else 0.0

            import os
            memory_bytes = 0
            try:
                with open("/proc/self/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            memory_bytes = int(line.split()[1]) * 1024
                            break
            except Exception:
                pass

            return {
                "uptime_seconds": round(uptime, 1),
                "total_requests": total_requests,
                "avg_latency_ms": round(total_latency / total_requests, 2) if total_requests > 0 else 0.0,
                "total_errors": total_errors,
                "error_rate": round(total_errors / total_requests * 100, 2) if total_requests > 0 else 0.0,
                "latency_buckets": self._latency.buckets.copy(),
                "per_endpoint": per_endpoint,
                "tool_executions": self._tool_executions,
                "workflow_executions": self._workflow_executions,
                "missions_completed": self._missions_completed,
                "missions_failed": self._missions_failed,
                "model_calls": self._model_calls,
                "model_avg_latency_ms": round(model_avg, 2),
                "websocket_current": self._websocket_connections,
                "websocket_peak": self._websocket_peak,
                "memory_usage_bytes": memory_bytes,
            }


_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _metrics
