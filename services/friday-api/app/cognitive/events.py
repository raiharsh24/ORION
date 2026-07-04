from typing import Dict, Any, Optional
from app.events.events import FridayEvent


class GoalCreated(FridayEvent):
    def __init__(self, goal_id: str, objective: str,
                 parent_id: Optional[str] = None,
                 priority: float = 5.0) -> None:
        super().__init__(topic="cognitive.goal.created", data={
            "goal_id": goal_id,
            "objective": objective,
            "parent_id": parent_id,
            "priority": priority,
        })


class GoalUpdated(FridayEvent):
    def __init__(self, goal_id: str, objective: str,
                 status: str, progress_pct: float) -> None:
        super().__init__(topic="cognitive.goal.updated", data={
            "goal_id": goal_id,
            "objective": objective,
            "status": status,
            "progress_pct": progress_pct,
        })


class MilestoneCompleted(FridayEvent):
    def __init__(self, goal_id: str, milestone_id: str,
                 milestone_name: str,
                 progress_pct: float) -> None:
        super().__init__(topic="cognitive.goal.milestone_completed", data={
            "goal_id": goal_id,
            "milestone_id": milestone_id,
            "milestone_name": milestone_name,
            "progress_pct": progress_pct,
        })


class SchedulerStarted(FridayEvent):
    def __init__(self) -> None:
        super().__init__(topic="cognitive.scheduler.started", data={})


class SchedulerStopped(FridayEvent):
    def __init__(self) -> None:
        super().__init__(topic="cognitive.scheduler.stopped", data={})


class MissionDelegated(FridayEvent):
    def __init__(self, mission_id: str, objective: str,
                 workflow_type: str,
                 agent_ids: list) -> None:
        super().__init__(topic="cognitive.mission.delegated", data={
            "mission_id": mission_id,
            "objective": objective,
            "workflow_type": workflow_type,
            "agent_ids": agent_ids,
        })


class MissionRecovered(FridayEvent):
    def __init__(self, mission_id: str, workflow_id: str,
                 strategy: str) -> None:
        super().__init__(topic="cognitive.mission.recovered", data={
            "mission_id": mission_id,
            "workflow_id": workflow_id,
            "strategy": strategy,
        })


class LearningUpdated(FridayEvent):
    def __init__(self, learning_type: str,
                 summary: str) -> None:
        super().__init__(topic="cognitive.learning.updated", data={
            "learning_type": learning_type,
            "summary": summary,
        })
