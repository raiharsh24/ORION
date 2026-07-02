from typing import Dict, Any
from app.events.events import FridayEvent


class MissionStarted(FridayEvent):
    def __init__(self, mission_id: str, user_request: str,
                 intent: str) -> None:
        super().__init__(topic="MissionStarted", data={
            "mission_id": mission_id, "user_request": user_request,
            "intent": intent,
        })


class MissionPaused(FridayEvent):
    def __init__(self, mission_id: str, reason: str = "") -> None:
        super().__init__(topic="MissionPaused", data={
            "mission_id": mission_id, "reason": reason,
        })


class MissionResumed(FridayEvent):
    def __init__(self, mission_id: str) -> None:
        super().__init__(topic="MissionResumed", data={
            "mission_id": mission_id,
        })


class MissionCompleted(FridayEvent):
    def __init__(self, mission_id: str, duration_ms: float,
                 stages: int) -> None:
        super().__init__(topic="MissionCompleted", data={
            "mission_id": mission_id, "duration_ms": duration_ms,
            "stages": stages,
        })


class MissionFailed(FridayEvent):
    def __init__(self, mission_id: str, stage: str,
                 error: str) -> None:
        super().__init__(topic="MissionFailed", data={
            "mission_id": mission_id, "stage": stage, "error": error,
        })


class MissionRecovered(FridayEvent):
    def __init__(self, mission_id: str, recovery_count: int) -> None:
        super().__init__(topic="MissionRecovered", data={
            "mission_id": mission_id, "recovery_count": recovery_count,
        })


class MissionArchived(FridayEvent):
    def __init__(self, mission_id: str) -> None:
        super().__init__(topic="MissionArchived", data={
            "mission_id": mission_id,
        })
