from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


@dataclass
class CapabilityEngineHealth:
    total_capabilities: int = 0
    active_capabilities: int = 0
    deprecated_capabilities: int = 0
    disabled_capabilities: int = 0
    resolved_count: int = 0
    execution_count: int = 0
    failure_count: int = 0
    success_rate: float = 100.0
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)
