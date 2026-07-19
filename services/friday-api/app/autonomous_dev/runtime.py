from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger

from app.events.bus import EventBus
from app.autonomous_dev.models import AutonomousGoal, AutonomousTask
from app.autonomous_dev.events import AutonomousTaskStatusChanged

# Forward-referencing stubs for components to be implemented
class AutonomousPlanner:
    async def create_plan(self, goal: AutonomousGoal, existing_tasks: List[AutonomousTask]) -> List[AutonomousTask]:
        logger.warning("Using stubbed AutonomousPlanner.")
        return []

class AutonomousExecutor:
    async def execute_task(self, task: AutonomousTask) -> Any:
        logger.warning("Using stubbed AutonomousExecutor.")
        return "Stubbed execution result."

class AutonomousReflection:
     async def reflect(self, goal: AutonomousGoal, completed_task: AutonomousTask):
        logger.warning("Using stubbed AutonomousReflection.")
        pass

class AutonomousRuntime:
    """
    Manages the execution lifecycle of a single autonomous goal.
    This contains the core 'Observe, Think, Plan, Execute, Reflect' loop.
    """
    def __init__(self,
                 goal: AutonomousGoal,
                 event_bus: Optional[EventBus] = None,
                 workspace_manager: Optional[Any] = None,
                 knowledge_engine: Optional[Any] = None,
                 planner: Optional[Any] = None,
                 executor: Optional[Any] = None,
                 reflection_engine: Optional[Any] = None,
                 memory_engine: Optional[Any] = None):
        self.goal = goal
        self._event_bus = event_bus
        self._workspace_manager = workspace_manager
        self._knowledge_engine = knowledge_engine
        self._planner = planner or AutonomousPlanner()
        self._executor = executor or AutonomousExecutor()
        self._reflection = reflection_engine or AutonomousReflection()
        self._memory_engine = memory_engine

        self._tasks: Dict[str, AutonomousTask] = {}
        self._running = False
        self._main_loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def run_loop(self):
        """The main autonomous loop."""
        self._running = True
        logger.info(f"AutonomousRuntime for goal '{self.goal.id}' started.")

        while not self._stop_event.is_set():
            try:
                # 1. OBSERVE: What is the current state?
                # In a real implementation, this would involve scanning the workspace
                # and knowledge graph for changes. For now, we observe our own state.
                current_state = self.get_current_state()
                logger.info(f"[{self.goal.id}] OBSERVE: {len(self._tasks)} tasks, {len(current_state['completed'])} completed.")

                # 2. THINK/PLAN: What should we do next?
                new_tasks = await self._planner.create_plan(self.goal, list(self._tasks.values()))
                for task in new_tasks:
                    if task.id not in self._tasks:
                        self._tasks[task.id] = task
                        logger.info(f"[{self.goal.id}] PLAN: New task added - {task.description}")

                # 3. EXECUTE: Pick a task and run it.
                next_task = self._select_next_task()
                if next_task:
                    logger.info(f"[{self.goal.id}] EXECUTE: Starting task '{next_task.id}': {next_task.description}")
                    next_task.status = "in_progress"
                    if self._event_bus:
                        await self._event_bus.publish(AutonomousTaskStatusChanged(task_id=next_task.id, status=next_task.status))

                    # This is a simplified execution. A real executor would manage tools.
                    result = await self._executor.execute_task(next_task)
                    next_task.result = str(result)
                    next_task.status = "completed"

                    # 4. VALIDATE: (Implicit in executor) The executor determines success.

                    if self._event_bus:
                        await self._event_bus.publish(AutonomousTaskStatusChanged(task_id=next_task.id, status=next_task.status, result=next_task.result))
                    logger.info(f"[{self.goal.id}] EXECUTE: Completed task '{next_task.id}'.")

                    # 5. REFLECT & PERSIST
                    await self._reflection.reflect(self.goal, next_task)
                    logger.info(f"[{self.goal.id}] REFLECT: Reflection complete for task '{next_task.id}'.")

                else:
                    # No actionable tasks left. The goal is complete.
                    logger.info(f"[{self.goal.id}] No more actionable tasks. Goal completed.")
                    self.goal.status = "completed"
                    # In a real system, publish goal completion event here.
                    break

                # 6. REPEAT
                await asyncio.sleep(1) # Small delay to prevent tight loop spinning

            except asyncio.CancelledError:
                logger.info(f"AutonomousRuntime for goal '{self.goal.id}' was cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in autonomous loop for goal '{self.goal.id}': {e}", exc_info=True)
                self.goal.status = "failed"
                # In a real system, publish goal failure event here.
                break

        self._running = False
        logger.info(f"AutonomousRuntime for goal '{self.goal.id}' stopped.")

    def _select_next_task(self) -> Optional[AutonomousTask]:
        """A simple scheduler to pick the next available task."""
        for task in self._tasks.values():
            if task.status == "pending":
                # Check if dependencies are met
                deps_met = all(
                    self._tasks.get(dep_id, self._memory_engine.get_task(dep_id)).status == "completed"
                    for dep_id in task.dependencies
                )
                if deps_met:
                    return task
        return None

    def get_current_state(self) -> Dict[str, List[AutonomousTask]]:
        """Provides a snapshot of the current tasks."""
        state = {"pending": [], "in_progress": [], "completed": []}
        for task in self._tasks.values():
            state.get(task.status, []).append(task)
        return state

    async def stop(self):
        """Signals the main loop to stop."""
        self._stop_event.set()

    def get_tasks(self) -> Dict[str, AutonomousTask]:
        return self._tasks
