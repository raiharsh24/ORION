from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class ExecutionPlan(BaseModel):
    """
    Structured plan detailing intent, required systems, steps, and priority.
    Maintains compatibility with legacy ToolPlan outputs via custom fields.
    """
    intent: str
    goal: str
    memoryRequired: bool
    toolRequired: bool
    clarificationRequired: bool
    capabilities: List[str] = Field(default_factory=list)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    priority: str = "medium"  # "low", "medium", "high"
    confidence: float = 1.0

    # Backwards compatibility properties (ToolPlan interface)
    tool_name: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
