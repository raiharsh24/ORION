from typing import Dict, Any
from app.events.events import FridayEvent
from app.intent.types import IntentType


class IntentAnalyzed(FridayEvent):
    def __init__(self, request: str, intent: IntentType, confidence: float, reasoning: str) -> None:
        super().__init__(topic="IntentAnalyzed", data={
            "request": request,
            "intent": intent.value,
            "confidence": confidence,
            "reasoning": reasoning,
        })
