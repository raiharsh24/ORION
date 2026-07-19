from app.events.events import FridayEvent
from typing import Dict, Any

class AutonomousGoalCreated(FridayEvent):
    def __init__(self, goal_id: str, prompt: str):
        super().__init__("autonomous.goal.created", {"goal_id": goal_id, "prompt": prompt})

class AutonomousGoalStatusChanged(FridayEvent):
    def __init__(self, goal_id: str, status: str):
        super().__init__("autonomous.goal.status", {"goal_id": goal_id, "status": status})

class AutonomousTaskCreated(FridayEvent):
    def __init__(self, task_id: str, goal_id: str, description: str):
        super().__init__("autonomous.task.created", {"task_id": task_id, "goal_id": goal_id, "description": description})

class AutonomousTaskStatusChanged(FridayEvent):
    def __init__(self, task_id: str, status: str, result: Any = None):
        super().__init__("autonomous.task.status", {"task_id": task_id, "status": status, "result": result})

class AutonomousPlanGenerated(FridayEvent):
    def __init__(self, goal_id: str, plan: Dict[str, Any]):
        super().__init__("autonomous.plan.generated", {"goal_id": goal_id, "plan": plan})

class AutonomousStepExecuting(FridayEvent):
    def __init__(self, task_id: str, tool_name: str, tool_args: Dict[str, Any]):
        super().__init__("autonomous.step.executing", {"task_id": task_id, "tool_name": tool_name, "tool_args": tool_args})

class AutonomousStepCompleted(FridayEvent):
    def __init__(self, task_id: str, tool_name: str, result: Any, success: bool):
        super().__init__("autonomous.step.completed", {"task_id": task_id, "tool_name": tool_name, "result": result, "success": success})

class AutonomousReflectionGenerated(FridayEvent):
    def __init__(self, goal_id: str, task_id: str, reflection: Dict[str, Any]):
        super().__init__("autonomous.reflection.generated", {"goal_id": goal_id, "task_id": task_id, "reflection": reflection})
