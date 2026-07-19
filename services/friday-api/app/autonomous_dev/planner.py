from typing import List, Optional, Any
from uuid import uuid4
from loguru import logger

from app.autonomous_dev.models import AutonomousGoal, AutonomousTask

class AutonomousPlanner:
    """
    Generates a sequence of tasks to achieve a high-level goal.
    """
    def __init__(self, memory_engine: Optional[Any] = None):
        # In a future version, the planner would use the memory_engine
        # to recall past successful plans.
        self._memory_engine = memory_engine
        logger.info("AutonomousPlanner initialized.")

    async def create_plan(self, goal: AutonomousGoal, existing_tasks: List[AutonomousTask]) -> List[AutonomousTask]:
        """
        Creates a new plan or refines an existing one.
        For this vertical slice, we use a simple rule-based planner.
        """
        if any(t.description == "Inspect and analyze the current workspace." for t in existing_tasks):
            # Plan already exists, no new tasks needed.
            return []

        if "inspect" in goal.prompt.lower():
            logger.info(f"Planner creating 'inspect' plan for goal {goal.id}")
            task_id = str(uuid4())
            analysis_task = AutonomousTask(
                id=task_id,
                goal_id=goal.id,
                description="Inspect and analyze the current workspace.",
                dependencies=[]
            )
            return [analysis_task]

        # In the future, this would involve LLM calls or more complex logic.
        logger.warning(f"No planning rule found for goal prompt: '{goal.prompt}'")
        return []
