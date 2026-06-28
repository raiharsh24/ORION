import uuid
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from loguru import logger

from app.agents.models import AgentStatus, AgentInfo, AgentTask, AgentMessage
from app.agents.events import (
    AgentStatusChanged, AgentTaskStarted, AgentTaskCompleted,
    AgentTaskFailed, AgentTaskCancelled, AgentTaskTimeout,
    AgentMessageSent, AgentMessageReceived, AgentError
)


class BaseAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        description: str = ""
    ) -> None:
        self._agent_id = agent_id
        self._name = name
        self._capabilities = capabilities or []
        self._permissions = permissions or []
        self._description = description
        self._status = AgentStatus.STOPPED
        self._current_task: Optional[AgentTask] = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._started_at: Optional[datetime] = None
        self._metadata: Dict[str, Any] = {}
        self._event_bus = None
        self._message_bus = None
        self._context = None

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def capabilities(self) -> List[str]:
        return self._capabilities

    @property
    def permissions(self) -> List[str]:
        return self._permissions

    @property
    def info(self) -> AgentInfo:
        uptime = 0.0
        if self._started_at:
            uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()
        return AgentInfo(
            agent_id=self._agent_id,
            name=self._name,
            status=self._status,
            capabilities=self._capabilities,
            permissions=self._permissions,
            description=self._description,
            health="HEALTHY" if self._status != AgentStatus.ERROR else "ERROR",
            current_task=self._current_task.task_id if self._current_task else None,
            tasks_completed=self._tasks_completed,
            tasks_failed=self._tasks_failed,
            uptime=uptime,
            started_at=self._started_at,
            metadata=self._metadata
        )

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    def set_message_bus(self, message_bus: Any) -> None:
        self._message_bus = message_bus

    def set_context(self, context: Any) -> None:
        self._context = context

    def _set_status(self, new_status: AgentStatus) -> None:
        old = self._status
        self._status = new_status
        if self._event_bus:
            self._event_bus and self._event_bus.publish_background(AgentStatusChanged(self._agent_id, old.value, new_status.value))



    async def initialize(self) -> None:
        self._set_status(AgentStatus.INITIALIZING)
        logger.info(f"Agent '{self._name}' ({self._agent_id}) initializing.")

    async def start(self) -> None:
        self._started_at = datetime.now(timezone.utc)
        self._set_status(AgentStatus.IDLE)
        logger.info(f"Agent '{self._name}' ({self._agent_id}) started.")

    async def shutdown(self) -> None:
        self._current_task = None
        self._set_status(AgentStatus.STOPPED)
        logger.info(f"Agent '{self._name}' ({self._agent_id}) shut down.")

    async def pause(self) -> None:
        if self._status in (AgentStatus.IDLE, AgentStatus.BUSY):
            self._set_status(AgentStatus.PAUSED)
            logger.info(f"Agent '{self._name}' ({self._agent_id}) paused.")

    async def resume(self) -> None:
        if self._status == AgentStatus.PAUSED:
            self._set_status(AgentStatus.IDLE)
            logger.info(f"Agent '{self._name}' ({self._agent_id}) resumed.")

    async def process_task(self, task: AgentTask) -> Dict[str, Any]:
        if self._status == AgentStatus.STOPPED:
            raise RuntimeError(f"Agent '{self._agent_id}' is stopped and cannot process tasks.")

        if self._status == AgentStatus.PAUSED:
            raise RuntimeError(f"Agent '{self._agent_id}' is paused and cannot process tasks.")

        if self._status == AgentStatus.BUSY:
            raise RuntimeError(f"Agent '{self._agent_id}' is busy and cannot accept more tasks.")

        self._current_task = task
        task.agent_id = self._agent_id
        task.status = "RUNNING"
        task.started_at = datetime.now(timezone.utc)
        self._set_status(AgentStatus.BUSY)
        self._event_bus and self._event_bus.publish_background(AgentTaskStarted(task.task_id, self._agent_id))

        try:
            if task.timeout and task.timeout > 0:
                import asyncio
                result = await asyncio.wait_for(
                    self.execute_task(task),
                    timeout=task.timeout
                )
            else:
                result = await self.execute_task(task)

            task.status = "COMPLETED"
            task.completed_at = datetime.now(timezone.utc)
            task.result = result
            self._tasks_completed += 1
            self._event_bus and self._event_bus.publish_background(AgentTaskCompleted(task.task_id, self._agent_id, success=True))
            self._set_status(AgentStatus.IDLE)
            self._current_task = None
            return result

        except TimeoutError:
            task.status = "TIMEOUT"
            task.completed_at = datetime.now(timezone.utc)
            task.error = f"Task timed out after {task.timeout}s"
            self._tasks_failed += 1
            self._event_bus and self._event_bus.publish_background(AgentTaskTimeout(task.task_id, self._agent_id, task.timeout))
            self._set_status(AgentStatus.IDLE)
            self._current_task = None
            raise

        except Exception as e:
            error_msg = str(e)
            task.status = "FAILED"
            task.completed_at = datetime.now(timezone.utc)
            task.error = error_msg
            self._tasks_failed += 1
            self._event_bus and self._event_bus.publish_background(AgentTaskFailed(task.task_id, self._agent_id, error_msg))
            self._set_status(AgentStatus.IDLE)
            self._current_task = None
            raise

    async def cancel_task(self) -> None:
        if self._current_task:
            task_id = self._current_task.task_id
            self._current_task.status = "CANCELLED"
            self._current_task.completed_at = datetime.now(timezone.utc)
            self._event_bus and self._event_bus.publish_background(AgentTaskCancelled(task_id, self._agent_id))
            self._current_task = None
            self._set_status(AgentStatus.IDLE)
            logger.info(f"Agent '{self._name}' task {task_id} cancelled.")

    async def send_message(self, message: AgentMessage) -> None:
        if self._message_bus:
            await self._message_bus.send(message)
            self._event_bus and self._event_bus.publish_background(AgentMessageSent(
                message.message_id, self._agent_id,
                message.recipient or "*", message.type
            ))

    async def receive_message(self, message: AgentMessage) -> None:
        self._event_bus and self._event_bus.publish_background(AgentMessageReceived(
            message.message_id, self._agent_id,
            message.sender, message.type
        ))
        logger.debug(f"Agent '{self._name}' received message from {message.sender}: {message.type}")

    @abstractmethod
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        pass
