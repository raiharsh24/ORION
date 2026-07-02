from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime, timezone


@dataclass
class ToolRegistryHealth:
    status: str = "healthy"
    registered_tools: int = 0
    healthy_tools: int = 0
    unavailable_tools: int = 0
    permission_registry_size: int = 0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.registered_tools

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "registered_tools": self.registered_tools,
            "healthy_tools": self.healthy_tools,
            "unavailable_tools": self.unavailable_tools,
            "permission_registry_size": self.permission_registry_size,
            "last_checked": self.last_checked.isoformat(),
            "details": self.details,
        }
