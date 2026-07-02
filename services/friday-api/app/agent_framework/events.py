from typing import Dict, Any
from app.events.events import FridayEvent


class AgentRegistered(FridayEvent):
    def __init__(self, agent_id: str, name: str, role: str,
                 capabilities: list) -> None:
        super().__init__(topic="AgentRegistered", data={
            "agent_id": agent_id, "name": name, "role": role,
            "capabilities": capabilities,
        })


class AgentUnregistered(FridayEvent):
    def __init__(self, agent_id: str, name: str) -> None:
        super().__init__(topic="AgentUnregistered", data={
            "agent_id": agent_id, "name": name,
        })


class AgentStateChanged(FridayEvent):
    def __init__(self, agent_id: str, old_state: str,
                 new_state: str) -> None:
        super().__init__(topic="AgentStateChanged", data={
            "agent_id": agent_id,
            "old_state": old_state, "new_state": new_state,
        })


class AgentTaskStarted(FridayEvent):
    def __init__(self, agent_id: str, task_id: str,
                 task_type: str) -> None:
        super().__init__(topic="AgentTaskStarted", data={
            "agent_id": agent_id, "task_id": task_id,
            "task_type": task_type,
        })


class AgentTaskCompleted(FridayEvent):
    def __init__(self, agent_id: str, task_id: str,
                 result: str = "") -> None:
        super().__init__(topic="AgentTaskCompleted", data={
            "agent_id": agent_id, "task_id": task_id,
            "result": result,
        })


class AgentTaskFailed(FridayEvent):
    def __init__(self, agent_id: str, task_id: str,
                 error: str) -> None:
        super().__init__(topic="AgentTaskFailed", data={
            "agent_id": agent_id, "task_id": task_id,
            "error": error,
        })


class AgentMessageSent(FridayEvent):
    def __init__(self, sender: str, recipient: str,
                 message_type: str) -> None:
        super().__init__(topic="AgentMessageSent", data={
            "sender": sender, "recipient": recipient,
            "message_type": message_type,
        })


class AgentHealthChanged(FridayEvent):
    def __init__(self, agent_id: str, old_status: str,
                 new_status: str) -> None:
        super().__init__(topic="AgentHealthChanged", data={
            "agent_id": agent_id,
            "old_status": old_status, "new_status": new_status,
        })


class DelegationStarted(FridayEvent):
    def __init__(self, task_id: str, parent_task_id: str,
                 agent_id: str, task_type: str) -> None:
        super().__init__(topic="DelegationStarted", data={
            "task_id": task_id, "parent_task_id": parent_task_id,
            "agent_id": agent_id, "task_type": task_type,
        })


class DelegationCompleted(FridayEvent):
    def __init__(self, task_id: str, agent_id: str,
                 status: str) -> None:
        super().__init__(topic="DelegationCompleted", data={
            "task_id": task_id, "agent_id": agent_id,
            "status": status,
        })


class TaskAssigned(FridayEvent):
    def __init__(self, task_id: str, agent_id: str,
                 task_type: str, priority: float = 0.0) -> None:
        super().__init__(topic="TaskAssigned", data={
            "task_id": task_id, "agent_id": agent_id,
            "task_type": task_type, "priority": priority,
        })


class TaskCompleted(FridayEvent):
    def __init__(self, task_id: str, agent_id: str,
                 result: str = "") -> None:
        super().__init__(topic="TaskCompleted", data={
            "task_id": task_id, "agent_id": agent_id,
            "result": result,
        })


class TaskRecovered(FridayEvent):
    def __init__(self, task_id: str, agent_id: str,
                 status: str) -> None:
        super().__init__(topic="TaskRecovered", data={
            "task_id": task_id, "agent_id": agent_id,
            "status": status,
        })


class ConsensusReached(FridayEvent):
    def __init__(self, proposal: str, strategy: str,
                 accepted: bool, confidence: float) -> None:
        super().__init__(topic="ConsensusReached", data={
            "proposal": proposal, "strategy": strategy,
            "accepted": accepted, "confidence": confidence,
        })


class BlackboardUpdated(FridayEvent):
    def __init__(self, key: str, value: str, writer: str,
                 version: int) -> None:
        super().__init__(topic="BlackboardUpdated", data={
            "key": key, "value": str(value)[:200],
            "writer": writer, "version": version,
        })


class CheckpointCreated(FridayEvent):
    def __init__(self, timestamp: float,
                 agent_count: int, task_count: int) -> None:
        super().__init__(topic="CheckpointCreated", data={
            "timestamp": timestamp, "agent_count": agent_count,
            "task_count": task_count,
        })
