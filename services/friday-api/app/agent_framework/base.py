from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from app.agent_framework.state import AgentState, StateMachine


@dataclass
class AgentCapability:
    name: str
    version: str = "1.0.0"
    description: str = ""
    tools: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleDefinition:
    role: str
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class MissionAssignment:
    mission_id: str
    objective: str
    assigned_by: str = ""
    assigned_at: Optional[datetime] = None
    priority: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    deadline: Optional[datetime] = None


@dataclass
class AgentTelemetry:
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time_ms: float = 0.0
    average_execution_time_ms: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    last_active: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class AgentModel:
    agent_id: str
    name: str
    role: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    mission: Optional[MissionAssignment] = None
    state: AgentState = AgentState.IDLE
    priority: int = 0
    memory_scope: str = "session"
    permissions: List[str] = field(default_factory=list)
    health_status: str = "healthy"
    telemetry: AgentTelemetry = field(default_factory=AgentTelemetry)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def capability_names(self) -> List[str]:
        return [c.name for c in self.capabilities]

    @property
    def is_idle(self) -> bool:
        return self.state == AgentState.IDLE

    @property
    def is_busy(self) -> bool:
        return self.state in (AgentState.PLANNING, AgentState.RUNNING, AgentState.WAITING)

    @property
    def is_terminal(self) -> bool:
        return self.state in (AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED)

    def has_capability(self, capability: str) -> bool:
        return any(c.name == capability for c in self.capabilities)

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def can_execute(self, required_capability: str) -> bool:
        return self.has_capability(required_capability) and self.is_idle
