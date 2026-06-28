import re
from typing import Dict, Any, Optional
from app.friday.intent import IntentType
from pydantic import BaseModel

class ToolPlan(BaseModel):
    """
    Structured container for tool choices and kwargs.
    """
    tool_name: str
    args: Dict[str, Any]
    reasoning: str

from app.friday.planner_schema import ExecutionPlan
from app.friday.planner_engine import PlannerEngine

# Legacy Planner alias to new PlannerEngine for runtime compatibility
Planner = PlannerEngine
