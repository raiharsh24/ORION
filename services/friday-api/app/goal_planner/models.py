from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


@dataclass
class GoalTask:
    id: str
    title: str
    description: str
    required_capability: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    estimated_complexity: float = 1.0
    parallel_group: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GoalPlan:
    goal: str
    tasks: List[GoalTask] = field(default_factory=list)
    intent: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def parallel_groups(self) -> List[str]:
        return list({t.parallel_group for t in self.tasks if t.parallel_group})

    @property
    def capabilities(self) -> List[str]:
        seen: set = set()
        result: List[str] = []
        for t in self.tasks:
            cap = t.required_capability
            if cap not in seen:
                seen.add(cap)
                result.append(cap)
        return result
