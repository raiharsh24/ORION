import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone
from loguru import logger

from app.agents.models import (
    AgentTask, AgentMessage, AgentInfo, CoordinatorResult,
    AgentStatus
)
from app.agents.events import (
    AgentTaskCreated, AgentTaskStarted, AgentTaskCompleted,
    AgentTaskFailed, AgentTaskCancelled, AgentTaskTimeout
)
from app.agents.base import BaseAgent
from app.agents.registry import AgentRegistry
from app.agents.bus import AgentMessageBus
from app.agents.scheduler import AgentScheduler
from app.agents.telemetry import AgentTelemetry
from app.agents.recovery import RetryHandler, CircuitBreaker, DeadLetterQueue


class AgentCoordinator:
    def __init__(
        self,
        registry: AgentRegistry,
        message_bus: AgentMessageBus,
        scheduler: AgentScheduler,
        telemetry: AgentTelemetry,
        shared_context: Any = None,
        event_bus: Any = None
    ) -> None:
        self._registry = registry
        self._message_bus = message_bus
        self._scheduler = scheduler
        self._telemetry = telemetry
        self._shared_context = shared_context
        self._event_bus = event_bus
        self._retry_handler = RetryHandler(max_retries=3, base_delay=1.0)
        self._dead_letter_queue = DeadLetterQueue(event_bus=event_bus)
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._pending_tasks: Dict[str, AgentTask] = {}
        self._active_delegations: Dict[str, asyncio.Task] = {}

    @property
    def dead_letter_queue(self) -> DeadLetterQueue:
        return self._dead_letter_queue

    async def route_task(self, task: AgentTask) -> Optional[str]:
        candidates = self._registry.discover(capability=task.type)
        if not candidates:
            candidates = self._registry.discover()
        if not candidates:
            logger.warning(f"No agents available for task type '{task.type}'")
            task.status = "FAILED"
            task.error = f"No agent found with capability '{task.type}'"
            self._publish_event(AgentTaskFailed(task.task_id, "", task.error))
            return None

        idle = [a for a in candidates if a.status == AgentStatus.IDLE]
        if not idle:
            logger.warning(f"No idle agents for task type '{task.type}', using least-loaded")
            candidates.sort(key=lambda a: a.info.tasks_completed - a.info.tasks_failed)
            chosen = candidates[-1] if candidates else candidates[0]
        else:
            idle.sort(key=lambda a: len(a.info.current_task or ""))
            chosen = idle[0]

        task.agent_id = chosen.agent_id
        task.trace_id = self._telemetry.start_trace(
            chosen.agent_id, f"task:{task.type}",
            trace_id=task.trace_id
        )
        self._pending_tasks[task.task_id] = task
        self._publish_event(AgentTaskCreated(task.task_id, task.type, chosen.agent_id))
        logger.info(f"Routed task {task.task_id} ({task.type}) to agent '{chosen.name}'")
        return chosen.agent_id

    async def delegate(self, task: AgentTask) -> Dict[str, Any]:
        agent_id = await self.route_task(task)
        if not agent_id:
            raise RuntimeError(f"Could not route task {task.task_id}")

        agent = self._registry.get(agent_id)
        if not agent:
            raise RuntimeError(f"Agent '{agent_id}' not found after routing")

        circuit_name = f"{agent_id}:{task.type}"
        if circuit_name not in self._circuit_breakers:
            self._circuit_breakers[circuit_name] = CircuitBreaker(
                name=circuit_name,
                failure_threshold=5,
                reset_timeout=60.0,
                event_bus=self._event_bus
            )

        cb = self._circuit_breakers[circuit_name]

        async def execute_with_delegation() -> Dict[str, Any]:
            start = time.time()
            try:
                result = await agent.process_task(task)
                duration_ms = (time.time() - start) * 1000
                span_id = task.trace_id
                if span_id:
                    self._telemetry.end_trace(span_id, status="OK")
                self._telemetry.record_task_metrics(task, duration_ms, success=True)
                self._publish_event(AgentTaskCompleted(task.task_id, agent_id, success=True))
                return result
            except asyncio.TimeoutError:
                duration_ms = (time.time() - start) * 1000
                if task.trace_id:
                    self._telemetry.end_trace(task.trace_id, status="TIMEOUT")
                self._telemetry.record_task_metrics(task, duration_ms, success=False)
                raise
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                if task.trace_id:
                    self._telemetry.end_trace(task.trace_id, status="ERROR", error=str(e))
                self._telemetry.record_task_metrics(task, duration_ms, success=False)
                raise

        try:
            return await cb.call(
                lambda: self._retry_handler.execute(
                    execute_with_delegation,
                    task=task,
                    event_bus=self._event_bus
                )
            )
        except Exception as e:
            error_msg = str(e)
            if task.agent_id:
                msg = AgentMessage(
                    message_id=uuid.uuid4().hex,
                    sender="coordinator",
                    recipient=task.agent_id,
                    type="ERROR",
                    payload={"task_id": task.task_id, "error": error_msg}
                )
                await self._dead_letter_queue.put(msg, error_msg)
            raise RuntimeError(f"Delegation failed for task {task.task_id}: {error_msg}") from e

    async def execute_parallel(self, tasks: List[AgentTask]) -> CoordinatorResult:
        total_start = time.time()
        coros = [self.delegate(t) for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        task_ids: List[str] = []
        success_results: List[Dict[str, Any]] = []
        errors: List[str] = []

        for task, result in zip(tasks, results):
            task_ids.append(task.task_id)
            if isinstance(result, Exception):
                errors.append(f"Task {task.task_id}: {result}")
            else:
                success_results.append(result)

        total_duration = (time.time() - total_start) * 1000
        return CoordinatorResult(
            success=len(errors) == 0,
            results=success_results,
            errors=errors,
            task_ids=task_ids,
            total_duration_ms=total_duration
        )

    async def cancel(self, agent_id: str) -> bool:
        agent = self._registry.get(agent_id)
        if not agent:
            return False
        await agent.cancel_task()
        delegation = self._active_delegations.pop(agent_id, None)
        if delegation:
            delegation.cancel()
        return True

    async def cancel_task(self, task_id: str) -> bool:
        task = self._pending_tasks.pop(task_id, None)
        if task:
            if task.agent_id:
                agent = self._registry.get(task.agent_id)
                if agent:
                    await agent.cancel_task()
            self._publish_event(AgentTaskCancelled(task_id, task.agent_id or ""))
            return True

        for agent in self._registry.discover():
            if agent._current_task and agent._current_task.task_id == task_id:
                await agent.cancel_task()
                self._publish_event(AgentTaskCancelled(task_id, agent.agent_id))
                return True

        return False

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self._pending_tasks.get(task_id)

    def list_pending_tasks(self) -> List[AgentTask]:
        return list(self._pending_tasks.values())

    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        return self._circuit_breakers.get(name)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "message": "AgentCoordinator operational.",
            "details": {
                "pending_tasks": len(self._pending_tasks),
                "active_delegations": len(self._active_delegations),
                "circuit_breakers": len(self._circuit_breakers),
                "dead_letter_queue_size": self._dead_letter_queue.count
            }
        }

    def _publish_event(self, event: Any) -> None:
        if not self._event_bus:
            return
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
            logger.error(f"AgentCoordinator event publish failed: {e}")
