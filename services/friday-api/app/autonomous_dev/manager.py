from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger

from app.events.bus import EventBus
from app.autonomous_dev.models import AutonomousGoal, AutonomousTask
from app.autonomous_dev.events import (
    AutonomousGoalCreated,
    AutonomousGoalStatusChanged,
)
from app.autonomous_dev.runtime import AutonomousRuntime

class AutonomousDevelopmentManager:
    """
    The central service for managing the Autonomous Development System.
    It orchestrates goals, tasks, and the main autonomous loop.
    """
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._goals: Dict[str, AutonomousGoal] = {}
        self._tasks: Dict[str, AutonomousTask] = {}
        self._active_runtimes: Dict[str, AutonomousRuntime] = {}
        self._lock = asyncio.Lock()
        logger.info("AutonomousDevelopmentManager initialized.")

    async def initialize(self):
        """Initializes the manager, loading any persisted state."""
        from app.kernel.kernel import FridayKernel
        kernel = FridayKernel.get_instance()
        memory_engine = kernel.get_service("memory_engine")
        if memory_engine and hasattr(memory_engine, "manager"):
            store = memory_engine.manager._store
            # Load goals
            try:
                goals_data = store.get("autonomous:goals")
                if goals_data:
                    for g_id, g_dict in goals_data.items():
                        self._goals[g_id] = AutonomousGoal(**g_dict)
                logger.info(f"Loaded {len(self._goals)} goals from persistent memory store.")
            except Exception as e:
                logger.error(f"Failed to load autonomous goals: {e}")

            # Load tasks
            try:
                tasks_data = store.get("autonomous:tasks")
                if tasks_data:
                    for t_id, t_dict in tasks_data.items():
                        self._tasks[t_id] = AutonomousTask(**t_dict)
                logger.info(f"Loaded {len(self._tasks)} tasks from persistent memory store.")
            except Exception as e:
                logger.error(f"Failed to load autonomous tasks: {e}")

        # Register event handlers for state persistence
        if self._event_bus:
            self._event_bus.subscribe("autonomous.goal.created", self._on_goal_event)
            self._event_bus.subscribe("autonomous.goal.status", self._on_goal_event)
            self._event_bus.subscribe("autonomous.task.status", self._on_task_event)
            self._event_bus.subscribe("autonomous.reflection.generated", self._on_reflection_event)

        logger.info("AutonomousDevelopmentManager service initialized.")

    def _persist(self):
        from app.kernel.kernel import FridayKernel
        kernel = FridayKernel.get_instance()
        memory_engine = kernel.get_service("memory_engine")
        if memory_engine and hasattr(memory_engine, "manager"):
            store = memory_engine.manager._store
            try:
                goals_data = {g_id: g.dict() for g_id, g in self._goals.items()}
                store.put("autonomous:goals", goals_data)
                
                # Collect both manager tasks and active runtime tasks
                all_tasks_map = {t_id: t for t_id, t in self._tasks.items()}
                for runtime in self._active_runtimes.values():
                    for t_id, t in runtime.get_tasks().items():
                        all_tasks_map[t_id] = t
                
                tasks_data = {t_id: t.dict() for t_id, t in all_tasks_map.items()}
                store.put("autonomous:tasks", tasks_data)
                
                if hasattr(store, "save"):
                    store.save()
            except Exception as e:
                logger.error(f"Failed to persist autonomous state: {e}")

    def _on_goal_event(self, event):
        """Triggered on goal creation or status changes."""
        goal_id = event.data.get("goal_id")
        if not goal_id:
            return
        status = event.data.get("status")
        prompt = event.data.get("prompt")
        
        if goal_id not in self._goals:
            self._goals[goal_id] = AutonomousGoal(id=goal_id, prompt=prompt or "", status=status or "active")
        else:
            if status:
                self._goals[goal_id].status = status
            if prompt:
                self._goals[goal_id].prompt = prompt
                
        self._persist()

    def _on_task_event(self, event):
        """Triggered on task status/result changes."""
        task_id = event.data.get("task_id")
        if not task_id:
            return
        status = event.data.get("status")
        result = event.data.get("result")
        
        # Find the task and update it
        task = self._tasks.get(task_id)
        if not task:
            # If not in manager tasks, search runtimes
            for runtime in self._active_runtimes.values():
                if task_id in runtime.get_tasks():
                    task = runtime.get_tasks().get(task_id)
                    break
        
        if task:
            if status:
                task.status = status
            if result is not None:
                task.result = str(result)
            self._persist()

    def _on_reflection_event(self, event):
        """Triggered when a reflection is generated."""
        self._persist()

    async def start_autonomous_goal(self, prompt: str) -> AutonomousGoal:
        """
        Creates a new autonomous goal and starts its execution loop.
        """
        from uuid import uuid4
        goal_id = str(uuid4())

        async with self._lock:
            if goal_id in self._active_runtimes:
                raise ValueError(f"Goal {goal_id} is already running.")

            goal = AutonomousGoal(id=goal_id, prompt=prompt, status="active")
            self._goals[goal_id] = goal

            # This is where we would get the real kernel services
            from app.kernel.kernel import FridayKernel
            kernel = FridayKernel.get_instance()

            runtime = AutonomousRuntime(
                goal=goal,
                event_bus=self._event_bus,
                workspace_manager=kernel.get_service("workspace_manager"),
                knowledge_engine=kernel.get_service("knowledge_engine"),
                planner=kernel.get_service("autonomous_planner"),
                executor=kernel.get_service("autonomous_executor"),
                reflection_engine=kernel.get_service("reflection_engine_v2"),
                memory_engine=kernel.get_service("memory_engine"),
            )
            self._active_runtimes[goal_id] = runtime

            # Start the main loop in the background
            asyncio.create_task(runtime.run_loop())

            if self._event_bus:
                await self._event_bus.publish(AutonomousGoalCreated(goal_id=goal.id, prompt=goal.prompt))
                await self._event_bus.publish(AutonomousGoalStatusChanged(goal_id=goal.id, status=goal.status))

            logger.info(f"Started autonomous goal {goal_id}: {prompt}")
            return goal

    async def stop_autonomous_goal(self, goal_id: str):
        """
        Stops a running autonomous goal.
        """
        async with self._lock:
            if goal_id not in self._active_runtimes:
                raise ValueError(f"Goal {goal_id} is not running.")

            runtime = self._active_runtimes.pop(goal_id)
            await runtime.stop()

            if goal_id in self._goals:
                self._goals[goal_id].status = "stopped"
                if self._event_bus:
                    await self._event_bus.publish(AutonomousGoalStatusChanged(goal_id=goal_id, status="stopped"))

            logger.info(f"Stopped autonomous goal {goal_id}.")

    def get_goal_status(self, goal_id: str) -> Optional[AutonomousGoal]:
        return self._goals.get(goal_id)

    def get_all_goals(self) -> List[AutonomousGoal]:
        return list(self._goals.values())

    def get_task_status(self, task_id: str) -> Optional[AutonomousTask]:
        # This would be expanded to get status from the active runtime
        for runtime in self._active_runtimes.values():
            if task_id in runtime.get_tasks():
                return runtime.get_tasks().get(task_id)
        return self._tasks.get(task_id) # Or check persisted tasks

    def get_all_tasks(self) -> List[AutonomousTask]:
        all_tasks = list(self._tasks.values())
        for runtime in self._active_runtimes.values():
            all_tasks.extend(runtime.get_tasks().values())
        return all_tasks

    def get_tasks_for_goal(self, goal_id: str) -> List[AutonomousTask]:
        return [t for t in self.get_all_tasks() if t.goal_id == goal_id]
