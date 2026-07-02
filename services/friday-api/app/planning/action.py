from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Action:
    action_id: str
    name: str
    description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    required_agents: int = 1
    estimated_cost: float = 1.0
    estimated_duration: float = 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)
