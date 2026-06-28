from app.events.events import OrionEvent


class AgentRegistered(OrionEvent):
    def __init__(self, agent_id: str, name: str, capabilities: list) -> None:
        super().__init__(topic="AgentRegistered", data={
            "agent_id": agent_id, "name": name, "capabilities": capabilities
        })


class AgentUnregistered(OrionEvent):
    def __init__(self, agent_id: str) -> None:
        super().__init__(topic="AgentUnregistered", data={"agent_id": agent_id})


class AgentStatusChanged(OrionEvent):
    def __init__(self, agent_id: str, old_status: str, new_status: str) -> None:
        super().__init__(topic="AgentStatusChanged", data={
            "agent_id": agent_id, "old_status": old_status, "new_status": new_status
        })


class AgentTaskCreated(OrionEvent):
    def __init__(self, task_id: str, task_type: str, agent_id: str = "") -> None:
        super().__init__(topic="AgentTaskCreated", data={
            "task_id": task_id, "type": task_type, "agent_id": agent_id
        })


class AgentTaskStarted(OrionEvent):
    def __init__(self, task_id: str, agent_id: str) -> None:
        super().__init__(topic="AgentTaskStarted", data={
            "task_id": task_id, "agent_id": agent_id
        })


class AgentTaskCompleted(OrionEvent):
    def __init__(self, task_id: str, agent_id: str, success: bool = True) -> None:
        super().__init__(topic="AgentTaskCompleted", data={
            "task_id": task_id, "agent_id": agent_id, "success": success
        })


class AgentTaskFailed(OrionEvent):
    def __init__(self, task_id: str, agent_id: str, error: str) -> None:
        super().__init__(topic="AgentTaskFailed", data={
            "task_id": task_id, "agent_id": agent_id, "error": error
        })


class AgentTaskCancelled(OrionEvent):
    def __init__(self, task_id: str, agent_id: str) -> None:
        super().__init__(topic="AgentTaskCancelled", data={
            "task_id": task_id, "agent_id": agent_id
        })


class AgentTaskTimeout(OrionEvent):
    def __init__(self, task_id: str, agent_id: str, timeout: float) -> None:
        super().__init__(topic="AgentTaskTimeout", data={
            "task_id": task_id, "agent_id": agent_id, "timeout": timeout
        })


class AgentMessageSent(OrionEvent):
    def __init__(self, message_id: str, sender: str, recipient: str, msg_type: str) -> None:
        super().__init__(topic="AgentMessageSent", data={
            "message_id": message_id, "sender": sender,
            "recipient": recipient, "type": msg_type
        })


class AgentMessageReceived(OrionEvent):
    def __init__(self, message_id: str, recipient: str, sender: str, msg_type: str) -> None:
        super().__init__(topic="AgentMessageReceived", data={
            "message_id": message_id, "recipient": recipient,
            "sender": sender, "type": msg_type
        })


class AgentError(OrionEvent):
    def __init__(self, agent_id: str, error: str) -> None:
        super().__init__(topic="AgentError", data={
            "agent_id": agent_id, "error": error
        })


class AgentJobScheduled(OrionEvent):
    def __init__(self, job_id: str, job_name: str, schedule_type: str) -> None:
        super().__init__(topic="AgentJobScheduled", data={
            "job_id": job_id, "name": job_name, "schedule_type": schedule_type
        })


class AgentJobCompleted(OrionEvent):
    def __init__(self, job_id: str, success: bool = True) -> None:
        super().__init__(topic="AgentJobCompleted", data={
            "job_id": job_id, "success": success
        })


class AgentCircuitBreakerTripped(OrionEvent):
    def __init__(self, name: str, failure_count: int) -> None:
        super().__init__(topic="AgentCircuitBreakerTripped", data={
            "name": name, "failure_count": failure_count
        })


class AgentDeadLetterMessage(OrionEvent):
    def __init__(self, message_id: str, error: str) -> None:
        super().__init__(topic="AgentDeadLetterMessage", data={
            "message_id": message_id, "error": error
        })
