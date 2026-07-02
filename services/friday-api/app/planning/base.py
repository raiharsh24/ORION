from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


@dataclass
class PlanStep:
    step_id: str
    action_id: str
    action_name: str = ""
    agent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    parallel_group: Optional[str] = None
    condition: Optional[str] = None
    fallback_step_id: Optional[str] = None
    estimated_cost: float = 1.0
    estimated_duration: float = 1.0
    status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    plan_id: str
    goal_id: str
    goal_name: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    total_cost: float = 0.0
    total_duration: float = 0.0
    risk_score: float = 0.0
    success_probability: float = 1.0
    constraint_score: float = 1.0
    status: str = "draft"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: PlanStep) -> None:
        self.steps.append(step)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "failed")
