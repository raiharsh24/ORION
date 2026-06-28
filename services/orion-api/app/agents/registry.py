from typing import Dict, Any, List, Optional
from loguru import logger

from app.agents.models import AgentInfo, AgentStatus
from app.agents.events import AgentRegistered, AgentUnregistered
from app.agents.base import BaseAgent


class AgentRegistry:
    def __init__(self, event_bus: Any = None, message_bus: Any = None) -> None:
        self._agents: Dict[str, BaseAgent] = {}
        self._event_bus = event_bus
        self._message_bus = message_bus

    async def register(self, agent: BaseAgent) -> None:
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent '{agent.agent_id}' is already registered.")

        agent.set_event_bus(self._event_bus)
        agent.set_message_bus(self._message_bus)

        await agent.initialize()
        self._agents[agent.agent_id] = agent
        await agent.start()

        self._publish_event(AgentRegistered(
            agent.agent_id, agent.name, agent.capabilities
        ))
        logger.info(f"AgentRegistry: registered '{agent.name}' ({agent.agent_id}) "
                     f"with capabilities: {agent.capabilities}")

    async def unregister(self, agent_id: str) -> None:
        agent = self._agents.pop(agent_id, None)
        if agent:
            await agent.shutdown()
            self._publish_event(AgentUnregistered(agent_id))
            logger.info(f"AgentRegistry: unregistered '{agent.name}' ({agent_id})")

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_id)

    def list(self) -> List[AgentInfo]:
        return [agent.info for agent in self._agents.values()]

    def discover(self, capability: Optional[str] = None) -> List[BaseAgent]:
        if not capability:
            return list(self._agents.values())
        return [
            agent for agent in self._agents.values()
            if capability in agent.capabilities
        ]

    def discover_by_permission(self, permission: str) -> List[BaseAgent]:
        return [
            agent for agent in self._agents.values()
            if permission in agent.permissions
        ]

    def get_idle_agents(self, capability: Optional[str] = None) -> List[BaseAgent]:
        agents = self.discover(capability)
        return [a for a in agents if a.status == AgentStatus.IDLE]

    def count(self) -> int:
        return len(self._agents)

    def health(self) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        for agent in self._agents.values():
            s = agent.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "status": "HEALTHY",
            "message": f"AgentRegistry: {self.count()} agents registered.",
            "details": {
                "total_agents": self.count(),
                "status_counts": status_counts,
                "agents": [a.agent_id for a in self._agents.values()]
            }
        }

    def _publish_event(self, event: Any) -> None:
        if not self._event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self._event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    asyncio.run(self._event_bus.publish(event))
            else:
                self._event_bus.publish(event)
        except Exception as e:
            logger.error(f"AgentRegistry event publish failed: {e}")
