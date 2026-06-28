from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime, timezone


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    ERROR = "ERROR"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    INITIALIZING = "INITIALIZING"


class AgentTask(BaseModel):
    task_id: str
    agent_id: Optional[str] = None
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    timeout: Optional[float] = None
    max_retries: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "PENDING"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None


class AgentMessage(BaseModel):
    message_id: str
    sender: str
    recipient: Optional[str] = None
    type: str = "EVENT"
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: Optional[float] = None


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.IDLE
    capabilities: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    description: str = ""
    health: str = "HEALTHY"
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    uptime: float = 0.0
    started_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScheduledJob(BaseModel):
    job_id: str
    agent_id: Optional[str] = None
    name: str
    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    schedule_type: str = "ONCE"
    interval_seconds: Optional[float] = None
    delay_seconds: Optional[float] = None
    max_runs: Optional[int] = None
    run_count: int = 0
    next_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    enabled: bool = True


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class AgentTrace(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    agent_id: Optional[str] = None
    operation: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: str = "OK"
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentMetrics(BaseModel):
    agent_id: str
    tasks_processed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    tasks_timed_out: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    last_activity: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CoordinatorResult(BaseModel):
    success: bool
    results: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    task_ids: List[str] = Field(default_factory=list)
    total_duration_ms: float = 0.0


class DeadLetterEntry(BaseModel):
    message_id: str
    original_message: AgentMessage
    error: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0
    last_error: Optional[str] = None
