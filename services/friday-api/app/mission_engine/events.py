from typing import Dict, Any
from app.events.events import FridayEvent


class MissionCreated(FridayEvent):
    def __init__(self, mission_id: str, name: str, total_workflows: int) -> None:
        super().__init__(topic="MissionCreated", data={
            "mission_id": mission_id,
            "name": name,
            "total_workflows": total_workflows,
        })


class MissionStarted(FridayEvent):
    def __init__(self, mission_id: str, name: str) -> None:
        super().__init__(topic="MissionStarted", data={
            "mission_id": mission_id,
            "name": name,
        })


class MissionProgressUpdated(FridayEvent):
    def __init__(self, mission_id: str, progress_pct: float,
                 completed: int, failed: int, remaining: int) -> None:
        super().__init__(topic="MissionProgressUpdated", data={
            "mission_id": mission_id,
            "progress_pct": progress_pct,
            "completed": completed,
            "failed": failed,
            "remaining": remaining,
        })


class MissionCheckpointSaved(FridayEvent):
    def __init__(self, mission_id: str, checkpoint_id: str,
                 completed_workflows: int, total_workflows: int) -> None:
        super().__init__(topic="MissionCheckpointSaved", data={
            "mission_id": mission_id,
            "checkpoint_id": checkpoint_id,
            "completed_workflows": completed_workflows,
            "total_workflows": total_workflows,
        })


class MissionCompleted(FridayEvent):
    def __init__(self, mission_id: str, name: str, total_duration_ms: float,
                 completed_workflows: int, total_workflows: int) -> None:
        super().__init__(topic="MissionCompleted", data={
            "mission_id": mission_id,
            "name": name,
            "total_duration_ms": total_duration_ms,
            "completed_workflows": completed_workflows,
            "total_workflows": total_workflows,
        })


class MissionFailed(FridayEvent):
    def __init__(self, mission_id: str, name: str, error: str,
                 completed_workflows: int, total_workflows: int) -> None:
        super().__init__(topic="MissionFailed", data={
            "mission_id": mission_id,
            "name": name,
            "error": error,
            "completed_workflows": completed_workflows,
            "total_workflows": total_workflows,
        })


class MissionCancelled(FridayEvent):
    def __init__(self, mission_id: str, name: str, reason: str,
                 completed_workflows: int, total_workflows: int) -> None:
        super().__init__(topic="MissionCancelled", data={
            "mission_id": mission_id,
            "name": name,
            "reason": reason,
            "completed_workflows": completed_workflows,
            "total_workflows": total_workflows,
        })
