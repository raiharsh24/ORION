from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ExecutionPlan:
    plan_id: str
    session_id: str
    stages: List[str] = field(default_factory=list)
    enabled_extractors: List[str] = field(default_factory=list)
    parallel_groups: List[List[str]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    estimated_latency_ms: float = 0.0
    estimated_tokens: int = 0
    cache_probability: float = 0.0
