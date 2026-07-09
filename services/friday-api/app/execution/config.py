from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay_ms: float = 500.0
    max_delay_ms: float = 10000.0
    backoff_multiplier: float = 2.0


@dataclass
class TimeoutPolicy:
    intent_timeout_s: float = 10.0
    planning_timeout_s: float = 30.0
    memory_timeout_s: float = 15.0
    tool_selection_timeout_s: float = 15.0
    execution_timeout_s: float = 120.0
    enrichment_timeout_s: float = 15.0
    llm_timeout_s: float = 60.0


@dataclass
class ExecutionConfig:
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_policy: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    track_progress: bool = True
    emit_events: bool = True
    collect_metrics: bool = True
    stage_overrides: Dict[str, Dict] = field(default_factory=dict)
