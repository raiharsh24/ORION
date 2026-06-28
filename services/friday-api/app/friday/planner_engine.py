from typing import Dict, Any, List, Optional
from loguru import logger

from app.friday.planner_manager import PlannerManager
from app.friday.planner_schema import ExecutionPlan
from app.friday.intent import IntentType

class PlannerEngine:
    """
    Main PlannerEngine service registered inside FridayServiceContainer.
    Exposes lifecycle hooks, health monitoring, and backward-compatible planning methods.
    """
    def __init__(self) -> None:
        self._manager: Optional[PlannerManager] = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Lifecycle initialize hook. Boostraps manager and EventBus bindings.
        """
        if self._initialized:
            return

        logger.info("Initializing PlannerEngine service...")
        from app.kernel.kernel import FridayKernel
        kernel = FridayKernel.get_instance()
        event_bus = kernel.get_service("event_bus")

        self._manager = PlannerManager(event_bus=event_bus)

        # Register EventBus subscribers
        self._event_bus = event_bus
        if self._event_bus:
            self._event_bus.subscribe("ConversationReceived", self._manager.on_conversation_received)
            self._event_bus.subscribe("MemoryRetrieved", self._manager.on_memory_retrieved)
            self._event_bus.subscribe("ToolCompleted", self._manager.on_tool_completed)
            self._event_bus.subscribe("MissionCompleted", self._manager.on_mission_completed)
            self._event_bus.subscribe("WorkflowCompleted", self._manager.on_workflow_completed)
            logger.info("PlannerEngine EventBus triggers bound successfully.")

        self._initialized = True
        logger.info("PlannerEngine initialized successfully.")

    async def start(self) -> None:
        """Lifecycle start hook."""
        logger.info("PlannerEngine service started.")

    async def shutdown(self) -> None:
        """Lifecycle shutdown hook."""
        logger.info("PlannerEngine service shut down.")
        if self._event_bus and self._manager:
            self._event_bus.unsubscribe("ConversationReceived", self._manager.on_conversation_received)
            self._event_bus.unsubscribe("MemoryRetrieved", self._manager.on_memory_retrieved)
            self._event_bus.unsubscribe("ToolCompleted", self._manager.on_tool_completed)
            self._event_bus.unsubscribe("MissionCompleted", self._manager.on_mission_completed)
            self._event_bus.unsubscribe("WorkflowCompleted", self._manager.on_workflow_completed)
        self._initialized = False

    def health(self) -> Dict[str, Any]:
        """Exposes health metrics for the subsystem health monitor."""
        if not self._initialized or not self._manager:
            return {
                "status": "WARNING",
                "message": "Planner Engine is not initialized."
            }

        avg_latency = 0.0
        if self._manager.planning_count > 0:
            avg_latency = self._manager.planning_latency_sum / self._manager.planning_count

        return {
            "status": "HEALTHY",
            "message": "Planner Engine running nominally.",
            "details": {
                "planning_count": self._manager.planning_count,
                "validation_failures": self._manager.validation_failures,
                "clarification_count": self._manager.clarification_count,
                "errors_count": self._manager.errors_count,
                "planning_latency_ms": round(avg_latency, 2)
            }
        }

    # ==========================================
    # Backward Compatibility Mappings
    # ==========================================
    async def plan(self, prompt: str, intent: IntentType) -> Optional[ExecutionPlan]:
        if not self._manager:
            logger.warning("PlannerEngine.plan called before initialize. Running lazy initialization.")
            self._manager = PlannerManager(event_bus=None)
        res = await self._manager.create_plan(prompt, intent)
        if not res.toolRequired:
            return None
        return res
