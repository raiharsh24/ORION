from typing import Dict, Any
from app.events.events import FridayEvent
from app.intent.types import IntentType


class StrategyResolved(FridayEvent):
    def __init__(self, intent: IntentType, strategy_name: str, token_budget: int) -> None:
        super().__init__(topic="StrategyResolved", data={
            "intent": intent.value,
            "strategy_name": strategy_name,
            "token_budget": token_budget,
        })
