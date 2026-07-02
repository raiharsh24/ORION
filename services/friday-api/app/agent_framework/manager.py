import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from app.agent_framework.base import (
    AgentModel, AgentCapability, MissionAssignment, AgentTelemetry,
)
from app.agent_framework.state import AgentState, StateMachine
from app.agent_framework.registry import AgentRegistry
from app.agent_framework.communication import CommunicationBus
from app.agent_framework.context import AgentContext
from app.agent_framework.scheduler import AgentScheduler
from app.agent_framework.permissions import PermissionManager
from app.agent_framework.health import (
    AgentFrameworkHealth, CoordinatorHealth, DelegationHealth,
    BlackboardHealth, PersistenceHealth, RecoveryHealth,
)
from app.agent_framework.events import (
    AgentRegistered, AgentUnregistered, AgentStateChanged,
    AgentTaskStarted, AgentTaskCompleted, AgentTaskFailed,
    AgentHealthChanged,
)
from app.agent_framework.locks import KeyLockManager
from app.agent_framework.blackboard import Blackboard
from app.agent_framework.delegation import DelegationManager
from app.agent_framework.coordinator import Coordinator
from app.agent_framework.priority import PriorityEngine, PriorityFactors
from app.agent_framework.consensus import ConsensusEngine, ConsensusStrategy
from app.agent_framework.persistence import PersistenceManager
from app.agent_framework.recovery import RecoveryManager
from app.agent_framework.metrics import MetricsCollector


class AgentManager:
    def __init__(self, persistence_base_path: Optional[str] = None):
        self.registry = AgentRegistry()
        self.communication = CommunicationBus()
        self.context = AgentContext()
        self.scheduler = AgentScheduler()
        self.permissions = PermissionManager()
        self.locks = KeyLockManager()
        self.blackboard = Blackboard(lock_manager=self.locks)
        self.delegation = DelegationManager()
        self.priority_engine = PriorityEngine()
        self.consensus = ConsensusEngine()
        self.metrics = MetricsCollector()
        self.persistence = PersistenceManager(base_path=persistence_base_path)
        self.coordinator = Coordinator(
            agent_manager=self,
            delegation_manager=self.delegation,
            blackboard=self.blackboard,
            priority_engine=self.priority_engine,
            metrics=self.metrics,
        )
        self.recovery = RecoveryManager(
            persistence=self.persistence,
            agent_manager=self,
            delegation=self.delegation,
            blackboard=self.blackboard,
            metrics=self.metrics,
        )
        self._event_bus = None
        self._pending_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._started = False

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus
        self.blackboard.set_update_callback(self._on_blackboard_update)

    def register_task_handler(self, task_type: str,
                               handler: Callable) -> None:
        self._task_handlers[task_type] = handler

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        await self.scheduler.start()

    async def shutdown(self) -> None:
        self._started = False
        await self.scheduler.shutdown()
        self._pending_tasks.clear()

    def _on_blackboard_update(self, key: str, value: Any,
                               writer: str) -> None:
        from app.agent_framework.events import BlackboardUpdated
        if self._event_bus:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    version = self.blackboard.get_version(key)
                    event = BlackboardUpdated(
                        key=key, value=str(value)[:200],
                        writer=writer, version=version,
                    )
                    loop.create_task(self._event_bus.publish(event))
            except RuntimeError:
                pass

    def create_agent(self, agent_id: str, name: str, role: str,
                     capabilities: Optional[List[AgentCapability]] = None,
                     tools: Optional[List[str]] = None,
                     permissions: Optional[List[str]] = None,
                     priority: int = 0,
                     memory_scope: str = "session") -> AgentModel:
        agent = AgentModel(
            agent_id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities or [],
            tools=tools or [],
            permissions=permissions or [],
            priority=priority,
            memory_scope=memory_scope,
            state=AgentState.IDLE,
        )
        self.registry.register(agent)
        for perm in (permissions or []):
            parts = perm.split(":")
            resource = parts[0] if len(parts) > 0 else perm
            action = parts[1] if len(parts) > 1 else "*"
            self.permissions.grant(agent_id, resource, action)
        self._publish_event("AgentRegistered", {
            "agent_id": agent_id, "name": name,
            "role": role, "capabilities": [c.name for c in (capabilities or [])],
        })
        return agent

    def destroy_agent(self, agent_id: str) -> bool:
        agent = self.registry.get(agent_id)
        if agent is None:
            return False
        agent.state = AgentState.CANCELLED
        result = self.registry.unregister(agent_id)
        self.permissions.clear_agent(agent_id)
        self.context.clear_agent(agent_id)
        self._publish_event("AgentUnregistered", {
            "agent_id": agent_id, "name": agent.name,
        })
        return result

    def transition_agent(self, agent_id: str,
                         new_state: AgentState) -> bool:
        agent = self.registry.get(agent_id)
        if agent is None:
            return False
        sm = StateMachine(agent.state)
        if not sm.transition(new_state):
            return False
        old_state = agent.state
        agent.state = new_state
        agent.updated_at = datetime.now(timezone.utc)
        self._publish_event("AgentStateChanged", {
            "agent_id": agent_id,
            "old_state": old_state.value if hasattr(old_state, "value") else str(old_state),
            "new_state": new_state.value if hasattr(new_state, "value") else str(new_state),
        })
        return True

    def assign_mission(self, agent_id: str, mission_id: str,
                       objective: str, assigned_by: str = "",
                       priority: int = 0,
                       context: Optional[Dict[str, Any]] = None) -> bool:
        agent = self.registry.get(agent_id)
        if agent is None:
            return False
        agent.mission = MissionAssignment(
            mission_id=mission_id,
            objective=objective,
            assigned_by=assigned_by,
            assigned_at=datetime.now(timezone.utc),
            priority=priority,
            context=context or {},
        )
        agent.updated_at = datetime.now(timezone.utc)
        return True

    def find_agents_for_task(self, required_capability: str) -> List[AgentModel]:
        candidates = self.registry.find_by_capability(required_capability)
        return sorted(
            [a for a in candidates if a.is_idle],
            key=lambda a: (
                -a.priority,
                a.telemetry.average_execution_time_ms,
            ),
        )

    async def execute_task(self, agent_id: str, task_type: str,
                           payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        agent = self.registry.get(agent_id)
        if agent is None:
            return None
        self.transition_agent(agent_id, AgentState.PLANNING)
        if not self.transition_agent(agent_id, AgentState.RUNNING):
            return None
        task_id = str(uuid.uuid4())
        self._pending_tasks[task_id] = {
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
            "started_at": datetime.now(timezone.utc),
        }
        self._publish_event("AgentTaskStarted", {
            "agent_id": agent_id, "task_id": task_id,
            "task_type": task_type,
        })
        handler = self._task_handlers.get(task_type)
        if handler is None:
            self._pending_tasks.pop(task_id, None)
            self.transition_agent(agent_id, AgentState.FAILED)
            self._publish_event("AgentTaskFailed", {
                "agent_id": agent_id, "task_id": task_id,
                "error": f"No handler for task type: {task_type}",
            })
            return None
        try:
            result = await handler(agent, payload)
            self._pending_tasks.pop(task_id, None)
            self.transition_agent(agent_id, AgentState.COMPLETED)
            self._publish_event("AgentTaskCompleted", {
                "agent_id": agent_id, "task_id": task_id,
                "result": str(result)[:200],
            })
            agent.telemetry.tasks_completed += 1
            agent.telemetry.last_active = datetime.now(timezone.utc)
            return result
        except Exception as e:
            self._pending_tasks.pop(task_id, None)
            self.transition_agent(agent_id, AgentState.FAILED)
            agent.telemetry.tasks_failed += 1
            agent.telemetry.errors.append(str(e))
            self._publish_event("AgentTaskFailed", {
                "agent_id": agent_id, "task_id": task_id,
                "error": str(e),
            })
            return None

    def get_agent(self, agent_id: str) -> Optional[AgentModel]:
        return self.registry.get(agent_id)

    def list_agents(self) -> List[AgentModel]:
        return self.registry.list_agents()

    def find_by_capability(self, capability: str) -> List[AgentModel]:
        return self.registry.find_by_capability(capability)

    def find_by_role(self, role: str) -> List[AgentModel]:
        return self.registry.find_by_role(role)

    def get_pending_tasks(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._pending_tasks)

    def _publish_event(self, topic: str, data: Dict[str, Any]) -> None:
        if self._event_bus is not None:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        from app.events.events import FridayEvent
                        event = FridayEvent(topic=topic, data=data)
                        loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    pass
            except Exception:
                pass

    def health(self) -> AgentFrameworkHealth:
        agents = self.registry.list_agents()
        state_counts = {}
        for a in agents:
            state_counts[a.state] = state_counts.get(a.state, 0) + 1

        total_exec_time = sum(
            a.telemetry.average_execution_time_ms for a in agents if a.telemetry.tasks_completed > 0
        )
        completed_count = sum(1 for a in agents if a.telemetry.tasks_completed > 0)
        avg_time = total_exec_time / completed_count if completed_count > 0 else 0.0

        return AgentFrameworkHealth(
            overall_status="healthy",
            running_agents=state_counts.get(AgentState.RUNNING, 0),
            idle_agents=state_counts.get(AgentState.IDLE, 0),
            failed_agents=state_counts.get(AgentState.FAILED, 0),
            planning_agents=state_counts.get(AgentState.PLANNING, 0),
            waiting_agents=state_counts.get(AgentState.WAITING, 0),
            paused_agents=state_counts.get(AgentState.PAUSED, 0),
            completed_agents=state_counts.get(AgentState.COMPLETED, 0),
            cancelled_agents=state_counts.get(AgentState.CANCELLED, 0),
            total_agents=self.registry.count(),
            queue_size=len(self._pending_tasks),
            pending_tasks=len(self._pending_tasks),
            average_execution_time_ms=avg_time,
            agents_with_context=len(self.context._data) if hasattr(self.context, '_data') else 0,
            bus_subscribers=self.communication.handler_count(),
            bus_pending_responses=len(self.communication._pending_responses) if hasattr(self.communication, '_pending_responses') else 0,
            scheduled_entries=len(self.scheduler.list_entries()),
            coordinator=self.coordinator.health() if hasattr(self.coordinator, 'health') else None,
            delegation=self.delegation.health() if hasattr(self.delegation, 'health') else None,
            blackboard=self.blackboard.health() if hasattr(self.blackboard, 'health') else None,
            persistence=self.persistence.health() if hasattr(self.persistence, 'health') else None,
            recovery=self.recovery.health() if hasattr(self.recovery, 'health') else None,
            agent_details=[
                {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "role": a.role,
                    "state": a.state.value if hasattr(a.state, 'value') else str(a.state),
                    "capabilities": a.capability_names,
                    "tasks_completed": a.telemetry.tasks_completed,
                    "tasks_failed": a.telemetry.tasks_failed,
                }
                for a in agents
            ],
        )
