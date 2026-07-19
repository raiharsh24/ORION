from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time

class AutonomousGoal(BaseModel):
    id: str = Field(description="Unique identifier for the goal.")
    prompt: str = Field(description="The high-level user prompt or objective.")
    status: str = Field(default="pending", description="Status: pending, active, completed, failed.")
    tasks: List[str] = Field(default_factory=list, description="List of task IDs associated with this goal.")
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None

class AutonomousTask(BaseModel):
    id: str = Field(description="Unique identifier for the task.")
    goal_id: str = Field(description="The goal this task belongs to.")
    description: str = Field(description="A detailed description of what the task should accomplish.")
    status: str = Field(default="pending", description="Status: pending, in_progress, completed, failed.")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs that must be completed first.")
    result: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

class ExecutionStep(BaseModel):
    task_id: str
    tool_name: str
    tool_args: Dict[str, Any]
    status: str = "pending" # pending, running, success, failure
    result: Optional[Any] = None

class ExecutionPlan(BaseModel):
    goal_id: str
    steps: List[ExecutionStep] = Field(default_factory=list)

class Reflection(BaseModel):
    goal_id: str
    task_id: str
    summary: str
    learnings: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    timestamp: float = Field(default_factory=time.time)
