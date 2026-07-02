from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.agent_framework.base import AgentModel, AgentCapability
from app.agent_framework.state import AgentState


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentModel] = {}
        self._capability_index: Dict[str, List[str]] = {}

    def register(self, agent: AgentModel) -> bool:
        if agent.agent_id in self._agents:
            return False
        agent.created_at = datetime.now(timezone.utc)
        agent.updated_at = datetime.now(timezone.utc)
        self._agents[agent.agent_id] = agent
        for cap in agent.capabilities:
            if cap.name not in self._capability_index:
                self._capability_index[cap.name] = []
            self._capability_index[cap.name].append(agent.agent_id)
        return True

    def unregister(self, agent_id: str) -> bool:
        agent = self._agents.pop(agent_id, None)
        if agent is None:
            return False
        for cap in agent.capabilities:
            agents = self._capability_index.get(cap.name, [])
            if agent_id in agents:
                agents.remove(agent_id)
        return True

    def get(self, agent_id: str) -> Optional[AgentModel]:
        return self._agents.get(agent_id)

    def update_state(self, agent_id: str, new_state: AgentState) -> bool:
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.state = new_state
        agent.updated_at = datetime.now(timezone.utc)
        return True

    def list_agents(self) -> List[AgentModel]:
        return list(self._agents.values())

    def list_ids(self) -> List[str]:
        return list(self._agents.keys())

    def find_by_capability(self, capability: str) -> List[AgentModel]:
        agent_ids = self._capability_index.get(capability, [])
        return [self._agents[a] for a in agent_ids if a in self._agents]

    def find_by_role(self, role: str) -> List[AgentModel]:
        return [a for a in self._agents.values() if a.role == role]

    def find_idle_by_capability(self, capability: str) -> List[AgentModel]:
        return [
            a for a in self.find_by_capability(capability)
            if a.is_idle
        ]

    def find_available(self) -> List[AgentModel]:
        return [a for a in self._agents.values() if a.is_idle]

    def count(self) -> int:
        return len(self._agents)

    def count_by_state(self, state: AgentState) -> int:
        return sum(1 for a in self._agents.values() if a.state == state)

    def get_capability_index(self) -> Dict[str, List[str]]:
        return dict(self._capability_index)

    def health(self) -> dict:
        return {
            "total_agents": self.count(),
            "agent_ids": self.list_ids(),
            "capabilities": list(self._capability_index.keys()),
            "status_counts": {
                state.value: self.count_by_state(state)
                for state in AgentState
            },
        }
