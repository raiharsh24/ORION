from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field

from app.agent_framework.blackboard import Blackboard

if TYPE_CHECKING:
    from app.mission_engine.base import MissionContext


@dataclass
class AgentToolPermissions:
    allowed_tools: List[str] = field(default_factory=lambda: [
        "knowledge.search", "memory", "filesystem", "terminal",
        "browser", "desktop", "clipboard", "tool.execute",
    ])
    restricted_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)


class SharedMissionContext:
    def __init__(self, mission_id: str,
                 knowledge_graph: Any = None,
                 episodic_memory: Any = None,
                 working_memory: Any = None) -> None:
        self._mission_id = mission_id
        self._blackboard = Blackboard()
        self._knowledge_graph = knowledge_graph
        self._episodic_memory = episodic_memory
        self._working_memory = working_memory or {}
        self._permissions = AgentToolPermissions()
        self._mission_context: Any = None

    @property
    def mission_id(self) -> str:
        return self._mission_id

    @property
    def blackboard(self) -> Blackboard:
        return self._blackboard

    @property
    def knowledge_graph(self) -> Any:
        return self._knowledge_graph

    @property
    def episodic_memory(self) -> Any:
        return self._episodic_memory

    @property
    def permissions(self) -> AgentToolPermissions:
        return self._permissions

    @permissions.setter
    def permissions(self, value: AgentToolPermissions) -> None:
        self._permissions = value

    def set_mission_context(self, ctx: Any) -> None:
        self._mission_context = ctx
        if hasattr(ctx, 'shared_data'):
            self._working_memory = dict(ctx.shared_data)

    def get_mission_context(self) -> Any:
        return self._mission_context

    def write_shared(self, key: str, value: Any, writer: str = "system") -> None:
        self._blackboard.post(key, value, writer=writer)
        if self._working_memory is not None:
            self._working_memory[key] = value

    def read_shared(self, key: str) -> Optional[Any]:
        entry = self._blackboard.read(key)
        if entry is not None:
            return entry.value
        return self._working_memory.get(key) if self._working_memory else None

    def get_all_shared(self) -> Dict[str, Any]:
        result = dict(self._working_memory or {})
        for key in self._blackboard.get_all_keys():
            if key not in result:
                entry = self._blackboard.read(key)
                if entry is not None:
                    result[key] = entry.value
        return result

    def restrict_tool(self, tool: str) -> None:
        if tool in self._permissions.allowed_tools:
            self._permissions.allowed_tools.remove(tool)
        if tool not in self._permissions.denied_tools:
            self._permissions.denied_tools.append(tool)

    def allow_tool(self, tool: str) -> None:
        if tool in self._permissions.denied_tools:
            self._permissions.denied_tools.remove(tool)
        if tool not in self._permissions.allowed_tools:
            self._permissions.allowed_tools.append(tool)

    def can_use_tool(self, tool: str) -> bool:
        return (
            tool in self._permissions.allowed_tools
            and tool not in self._permissions.denied_tools
        )

    def health(self) -> Dict[str, Any]:
        return {
            "mission_id": self._mission_id,
            "blackboard_entries": len(self._blackboard.get_all_keys()),
            "working_memory_keys": len(self._working_memory or {}),
            "has_knowledge_graph": self._knowledge_graph is not None,
            "has_episodic_memory": self._episodic_memory is not None,
            "denied_tools": list(self._permissions.denied_tools),
        }
