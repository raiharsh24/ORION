from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone


@dataclass
class PluginEngineHealth:
    total_plugins: int = 0
    enabled_plugins: int = 0
    loaded_plugins: int = 0
    failed_plugins: int = 0
    disabled_plugins: int = 0
    total_crashes: int = 0
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)
