import time
from typing import List, Dict, Any
from app.events.events import FridayEvent

class PlanCreated(FridayEvent):
    def __init__(self, plan_id: str, session_id: str, stages: List[str], enabled_extractors: List[str]) -> None:
        super().__init__(topic="PlanCreated", data={
            "plan_id": plan_id,
            "session_id": session_id,
            "stages": stages,
            "enabled_extractors": enabled_extractors,
            "timestamp": time.time(),
        })

class StageSkipped(FridayEvent):
    def __init__(self, plan_id: str, stage_name: str, reason: str) -> None:
        super().__init__(topic="StageSkipped", data={
            "plan_id": plan_id,
            "stage_name": stage_name,
            "reason": reason,
            "timestamp": time.time(),
        })

class PipelineOptimized(FridayEvent):
    def __init__(self, plan_id: str, optimization_actions: List[str]) -> None:
        super().__init__(topic="PipelineOptimized", data={
            "plan_id": plan_id,
            "optimization_actions": optimization_actions,
            "timestamp": time.time(),
        })

class PlanExecuted(FridayEvent):
    def __init__(self, plan_id: str, duration_ms: float, accuracy: float) -> None:
        super().__init__(topic="PlanExecuted", data={
            "plan_id": plan_id,
            "duration_ms": duration_ms,
            "accuracy": accuracy,
            "timestamp": time.time(),
        })
