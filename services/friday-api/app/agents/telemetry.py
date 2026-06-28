import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from loguru import logger

from app.agents.models import AgentTrace, AgentMetrics, AgentTask
from app.agents.events import (
    AgentTaskStarted, AgentTaskCompleted, AgentTaskFailed,
    AgentTaskCancelled, AgentTaskTimeout
)


class AgentTelemetry:
    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        self._traces: Dict[str, AgentTrace] = {}
        self._metrics: Dict[str, AgentMetrics] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 1000

    @property
    def traces(self) -> Dict[str, AgentTrace]:
        return dict(self._traces)

    @property
    def metrics(self) -> Dict[str, AgentMetrics]:
        return dict(self._metrics)

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def start_trace(
        self,
        agent_id: str,
        operation: str,
        parent_span_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> str:
        span_id = uuid.uuid4().hex
        tid = trace_id or uuid.uuid4().hex
        trace = AgentTrace(
            trace_id=tid,
            span_id=span_id,
            parent_span_id=parent_span_id,
            agent_id=agent_id,
            operation=operation,
            started_at=datetime.now(timezone.utc)
        )
        self._traces[span_id] = trace
        return span_id

    def end_trace(
        self,
        span_id: str,
        status: str = "OK",
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        trace = self._traces.get(span_id)
        if not trace:
            return
        trace.ended_at = datetime.now(timezone.utc)
        trace.duration_ms = (trace.ended_at - trace.started_at).total_seconds() * 1000
        trace.status = status
        trace.error = error
        if metadata:
            trace.metadata.update(metadata)
        self._record_history({
            "type": "trace",
            "span_id": span_id,
            "trace_id": trace.trace_id,
            "agent_id": trace.agent_id,
            "operation": trace.operation,
            "duration_ms": trace.duration_ms,
            "status": trace.status,
            "error": trace.error,
            "timestamp": trace.ended_at.isoformat() if trace.ended_at else None
        })

    def record_task_metrics(self, task: AgentTask, duration_ms: float, success: bool) -> None:
        agent_id = task.agent_id or "unknown"
        if agent_id not in self._metrics:
            self._metrics[agent_id] = AgentMetrics(agent_id=agent_id)

        m = self._metrics[agent_id]
        m.tasks_processed += 1
        m.total_duration_ms += duration_ms
        m.avg_duration_ms = m.total_duration_ms / m.tasks_processed if m.tasks_processed > 0 else 0.0
        m.last_activity = datetime.now(timezone.utc)

        if success:
            m.tasks_succeeded += 1
        else:
            m.tasks_failed += 1

        if task.status == "TIMEOUT":
            m.tasks_timed_out += 1

        m.updated_at = datetime.now(timezone.utc)

    def record_error(self, agent_id: str) -> None:
        if agent_id not in self._metrics:
            self._metrics[agent_id] = AgentMetrics(agent_id=agent_id)
        self._metrics[agent_id].errors += 1

    def record_message(self, agent_id: str, direction: str) -> None:
        if agent_id not in self._metrics:
            self._metrics[agent_id] = AgentMetrics(agent_id=agent_id)
        if direction == "sent":
            self._metrics[agent_id].messages_sent += 1
        else:
            self._metrics[agent_id].messages_received += 1

    def get_agent_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        return self._metrics.get(agent_id)

    def get_agent_traces(self, agent_id: str) -> List[AgentTrace]:
        return [t for t in self._traces.values() if t.agent_id == agent_id]

    def get_trace(self, span_id: str) -> Optional[AgentTrace]:
        return self._traces.get(span_id)

    def clear_traces(self) -> None:
        self._traces.clear()

    def clear_metrics(self) -> None:
        self._metrics.clear()

    def _record_history(self, entry: Dict[str, Any]) -> None:
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "message": "AgentTelemetry operational.",
            "details": {
                "active_traces": len(self._traces),
                "agents_with_metrics": len(self._metrics),
                "history_entries": len(self._history)
            }
        }
