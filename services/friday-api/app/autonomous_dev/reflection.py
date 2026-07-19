from typing import Any, Optional
from loguru import logger

from app.autonomous_dev.models import AutonomousGoal, AutonomousTask, Reflection
from app.memory.learning import LearningEngine
from app.events.bus import EventBus
from app.autonomous_dev.events import AutonomousReflectionGenerated

class AutonomousReflection:
    """
    Analyzes the outcome of a task, generates learnings, and persists them.
    This is the 'R' and 'P' in the O-T-P-E-V-R-P loop.
    """
    def __init__(self,
                 learning_engine: Optional[LearningEngine] = None,
                 event_bus: Optional[EventBus] = None):
        self._learning_engine = learning_engine
        self._event_bus = event_bus
        if not learning_engine:
            logger.warning("AutonomousReflection initialized without LearningEngine.")
        else:
            logger.info("AutonomousReflection initialized.")

    async def reflect(self, goal: AutonomousGoal, completed_task: AutonomousTask):
        """
        Performs reflection on a completed task.
        """
        if completed_task.status != "completed" or not completed_task.result:
            return

        logger.info(f"Reflecting on task '{completed_task.id}' for goal '{goal.id}'")

        # Create a structured reflection object
        reflection = self._create_reflection_from_result(goal, completed_task)

        # Persist the learning using the existing LearningEngine
        if self._learning_engine:
            await self._learning_engine.record_reflection(
                category="autonomous_task_completion",
                description=reflection.summary,
                severity="info",
                recommendation=", ".join(reflection.learnings),
                mission_id=goal.id, # Using goal_id as a proxy for mission_id
                metadata={"task_id": completed_task.id, "goal_prompt": goal.prompt}
            )
            logger.info(f"Persisted reflection for task '{completed_task.id}' to Memory/Learning Engine.")

        # Publish the reflection event
        if self._event_bus:
            await self._event_bus.publish(AutonomousReflectionGenerated(
                goal_id=goal.id,
                task_id=completed_task.id,
                reflection=reflection.dict()
            ))

    def _create_reflection_from_result(self, goal: AutonomousGoal, task: AutonomousTask) -> Reflection:
        """
        Generates a Reflection object from the task's execution result.
        """
        summary = "Unknown reflection"
        learnings = []
        confidence = 0.8 # Default confidence for successful mechanical tasks

        result_data = task.result
        if isinstance(result_data, str):
            try:
                import ast
                result_data = ast.literal_eval(result_data)
            except Exception:
                pass

        if "inspect and analyze" in task.description.lower() and isinstance(result_data, dict):
            project_name = result_data.get('project_name', 'Unnamed Project')
            files_indexed = result_data.get('files_indexed_now', 0)
            summary = f"Successfully inspected '{project_name}'. Indexed {files_indexed} files."
            learnings.append(f"The workspace structure for '{project_name}' has been vectorized for semantic search.")
            if files_indexed == 0:
                learnings.append("No new files were indexed, suggesting the knowledge base is up to date.")
                confidence = 0.9
            else:
                learnings.append(f"Updated knowledge base with {files_indexed} files.")

        return Reflection(
            goal_id=goal.id,
            task_id=task.id,
            summary=summary,
            learnings=learnings,
            confidence_score=confidence,
        )
