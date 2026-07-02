from typing import Dict, Any
from app.events.events import FridayEvent


class GoalCreated(FridayEvent):
    def __init__(self, goal_id: str, name: str, priority: float) -> None:
        super().__init__(topic="GoalCreated", data={
            "goal_id": goal_id, "name": name, "priority": priority,
        })


class GoalUpdated(FridayEvent):
    def __init__(self, goal_id: str, status: str) -> None:
        super().__init__(topic="GoalUpdated", data={
            "goal_id": goal_id, "status": status,
        })


class PlanGenerated(FridayEvent):
    def __init__(self, plan_id: str, goal_id: str,
                 step_count: int) -> None:
        super().__init__(topic="PlanGenerated", data={
            "plan_id": plan_id, "goal_id": goal_id,
            "step_count": step_count,
        })


class PlanValidated(FridayEvent):
    def __init__(self, plan_id: str, valid: bool,
                 error_count: int) -> None:
        super().__init__(topic="PlanValidated", data={
            "plan_id": plan_id, "valid": valid,
            "error_count": error_count,
        })


class PlanRejected(FridayEvent):
    def __init__(self, plan_id: str, reason: str) -> None:
        super().__init__(topic="PlanRejected", data={
            "plan_id": plan_id, "reason": reason,
        })


class PlanOptimized(FridayEvent):
    def __init__(self, plan_id: str, before_score: float,
                 after_score: float) -> None:
        super().__init__(topic="PlanOptimized", data={
            "plan_id": plan_id, "before_score": before_score,
            "after_score": after_score,
        })


class PlanExecuted(FridayEvent):
    def __init__(self, plan_id: str, goal_id: str,
                 success: bool) -> None:
        super().__init__(topic="PlanExecuted", data={
            "plan_id": plan_id, "goal_id": goal_id,
            "success": success,
        })


class PlanArchived(FridayEvent):
    def __init__(self, plan_id: str, goal_name: str) -> None:
        super().__init__(topic="PlanArchived", data={
            "plan_id": plan_id, "goal_name": goal_name,
        })
