from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class ExecutionStateModel:
    goal: str = ""
    planner_tasks: List[Dict[str, Any]] = field(default_factory=list)
    active_task: str = ""
    selected_tool: str = ""
    confidence: float = 0.0
    execution_stage: str = "idle"
    completed_tasks: List[str] = field(default_factory=list)
    stage_status: str = "idle"
    reflection_score: Optional[float] = None
    reflection_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "goal": self.goal,
            "planner_tasks": self.planner_tasks,
            "active_task": self.active_task,
            "selected_tool": self.selected_tool,
            "confidence": self.confidence,
            "execution_stage": self.execution_stage,
            "completed_tasks": self.completed_tasks,
            "stage_status": self.stage_status,
        }
        if self.reflection_score is not None:
            d["reflection_score"] = self.reflection_score
        if self.reflection_summary is not None:
            d["reflection_summary"] = self.reflection_summary
        return d
