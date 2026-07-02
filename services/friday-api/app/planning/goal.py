from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


@dataclass
class Goal:
    goal_id: str
    name: str
    description: str = ""
    priority: float = 5.0
    deadline: Optional[datetime] = None
    required_capabilities: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    estimated_cost: float = 0.0
    estimated_duration: float = 0.0
    parent_goal_id: Optional[str] = None
    child_goal_ids: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_child(self, child_id: str) -> None:
        if child_id not in self.child_goal_ids:
            self.child_goal_ids.append(child_id)
            self.updated_at = datetime.now(timezone.utc)

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_overdue(self) -> bool:
        if self.deadline is None:
            return False
        return datetime.now(timezone.utc) > self.deadline
