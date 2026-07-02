import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class PipelineRunMetadata:
    execution_id: str
    session_id: str
    timestamp: float = field(default_factory=time.time)
    total_latency_ms: float = 0.0
    stage_latencies: Dict[str, float] = field(default_factory=dict)
    extractor_latencies: Dict[str, float] = field(default_factory=dict)
    cache_hit_ratio: float = 0.0
    token_utilization: float = 0.0  # (actual tokens used) / (budget limit)
    context_reuse_ratio: float = 0.0
    incremental_update_ratio: float = 0.0
    status: str = "completed"  # "completed", "failed", "cancelled"
    error_message: Optional[str] = None
    is_timeout: bool = False

@dataclass
class OptimizationRecommendation:
    rule_name: str
    target: str
    action: str
    description: str
    priority: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    timestamp: float = field(default_factory=time.time)

@dataclass
class PerformanceAnomaly:
    anomaly_type: str
    metric_name: str
    value: float
    threshold: float
    description: str
    timestamp: float = field(default_factory=time.time)
