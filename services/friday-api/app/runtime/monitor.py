import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Observation:
    metric: str
    value: float
    workflow_id: str = ""
    tool_name: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class MonitorSnapshot:
    mission_id: str
    tool_failures: int = 0
    total_latency_ms: float = 0.0
    active_timeouts: int = 0
    avg_confidence: float = 1.0
    progress_pct: float = 0.0
    observation_count: int = 0
    warnings: List[str] = field(default_factory=list)


class ExecutionMonitor:
    """Continuously observes tool failures, latency, timeouts,
    resource usage, planner confidence, and mission progress.

    Feeds observations back into the AdaptiveScheduler for
    dynamic reordering decisions.
    """

    LATENCY_WARN_THRESHOLD_MS = 10000.0
    FAILURE_WARN_THRESHOLD = 3
    CONFIDENCE_WARN_THRESHOLD = 0.4

    def __init__(self) -> None:
        self._observations: Dict[str, List[Observation]] = {}
        self._latency_map: Dict[str, float] = {}
        self._failure_counts: Dict[str, int] = {}
        self._timeout_count = 0
        self._total_observations = 0

    def observe_tool(
        self,
        mission_id: str,
        workflow_id: str,
        tool_name: str,
        latency_ms: float,
        success: bool,
        confidence: float = 1.0,
    ) -> None:
        obs = Observation(
            metric="tool_latency" if success else "tool_failure",
            value=latency_ms,
            workflow_id=workflow_id,
            tool_name=tool_name,
        )
        self._record(mission_id, obs)
        self._total_observations += 1

        self._latency_map[workflow_id] = latency_ms

        if not success:
            key = f"{mission_id}:{tool_name}"
            self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

    def observe_latency(self, mission_id: str, workflow_id: str, ms: float) -> None:
        obs = Observation(
            metric="latency", value=ms, workflow_id=workflow_id
        )
        self._record(mission_id, obs)
        self._total_observations += 1
        self._latency_map[workflow_id] = ms

    def observe_timeout(self, mission_id: str, workflow_id: str) -> None:
        obs = Observation(
            metric="timeout", value=1.0, workflow_id=workflow_id
        )
        self._record(mission_id, obs)
        self._total_observations += 1
        self._timeout_count += 1

    def observe_confidence(self, mission_id: str, confidence: float) -> None:
        obs = Observation(
            metric="confidence", value=confidence, workflow_id=""
        )
        self._record(mission_id, obs)
        self._total_observations += 1

    def _record(self, mission_id: str, obs: Observation) -> None:
        if mission_id not in self._observations:
            self._observations[mission_id] = []
        self._observations[mission_id].append(obs)

    def snapshot(self, mission_id: str) -> MonitorSnapshot:
        obs_list = self._observations.get(mission_id, [])
        tool_failures = sum(
            1 for o in obs_list if o.metric == "tool_failure"
        )
        total_latency = sum(
            o.value for o in obs_list if o.metric in ("latency", "tool_latency")
        )
        timeouts = sum(
            1 for o in obs_list if o.metric == "timeout"
        )
        confidences = [
            o.value for o in obs_list if o.metric == "confidence"
        ]
        avg_conf = (
            sum(confidences) / len(confidences) if confidences else 1.0
        )

        warnings = []
        if total_latency > self.LATENCY_WARN_THRESHOLD_MS:
            warnings.append(
                f"High latency: {total_latency:.0f}ms"
            )
        if tool_failures > self.FAILURE_WARN_THRESHOLD:
            warnings.append(
                f"High failure rate: {tool_failures} failures"
            )
        if avg_conf < self.CONFIDENCE_WARN_THRESHOLD:
            warnings.append(
                f"Low confidence: {avg_conf:.2f}"
            )

        return MonitorSnapshot(
            mission_id=mission_id,
            tool_failures=tool_failures,
            total_latency_ms=total_latency,
            active_timeouts=timeouts,
            avg_confidence=avg_conf,
            observation_count=len(obs_list),
            warnings=warnings,
        )

    def get_latency_map(self) -> Dict[str, float]:
        return dict(self._latency_map)

    def get_failure_summary(self, mission_id: str) -> Dict[str, int]:
        return {
            tool: count
            for key, count in self._failure_counts.items()
            if key.startswith(f"{mission_id}:")
            for tool in [key.split(":", 1)[1]]
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_observations": self._total_observations,
            "timeout_count": self._timeout_count,
            "active_mission_count": len(self._observations),
        }
