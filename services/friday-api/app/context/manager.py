from typing import Dict, Optional
from loguru import logger

from app.intent.types import IntentType
from app.intent.events import IntentAnalyzed
from app.events.bus import EventBus
from app.context.base import ContextStrategy
from app.context.strategies import (
    ConversationStrategy,
    CodingStrategy,
    TerminalStrategy,
    DesktopStrategy,
    BrowserStrategy,
    WorkflowStrategy,
    PlanningStrategy,
    MemoryStrategy,
    SearchStrategy,
    VisionStrategy,
    UnknownStrategy,
)
from app.context.events import StrategyResolved


class StrategyManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False
        self._strategies: Dict[IntentType, ContextStrategy] = self._init_strategies()
        self._last_resolved: Optional[IntentType] = None

        if self._event_bus:
            self._event_bus.subscribe("IntentAnalyzed", self._on_intent_analyzed)

    @staticmethod
    def _init_strategies() -> Dict[IntentType, ContextStrategy]:
        instances: list[ContextStrategy] = [
            ConversationStrategy(),
            CodingStrategy(),
            TerminalStrategy(),
            DesktopStrategy(),
            BrowserStrategy(),
            WorkflowStrategy(),
            PlanningStrategy(),
            MemoryStrategy(),
            SearchStrategy(),
            VisionStrategy(),
            UnknownStrategy(),
        ]
        return {s.intent_type: s for s in instances}

    async def start(self) -> None:
        self._running = True
        logger.info("StrategyManager started.")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("StrategyManager shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "strategy_count": len(self._strategies),
                "last_resolved": self._last_resolved.value if self._last_resolved else None,
            },
        }

    async def _on_intent_analyzed(self, event: IntentAnalyzed) -> None:
        intent_str = event.data.get("intent", "unknown")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNKNOWN
        strategy = self.get_strategy(intent)
        self._last_resolved = intent

        if self._running and self._event_bus:
            config = strategy.get_config()
            resolve_event = StrategyResolved(
                intent=intent,
                strategy_name=strategy.__class__.__name__,
                token_budget=config.token_budget.total,
            )
            try:
                await self._event_bus.publish(resolve_event)
            except Exception as e:
                logger.error(f"Failed to publish StrategyResolved event: {e}")

    def get_strategy(self, intent: IntentType) -> ContextStrategy:
        return self._strategies.get(intent, self._strategies[IntentType.UNKNOWN])

    def list_strategies(self) -> Dict[IntentType, str]:
        return {it: s.__class__.__name__ for it, s in self._strategies.items()}
