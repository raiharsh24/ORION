import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone
from loguru import logger

from app.agents.models import (
    CircuitBreakerState, DeadLetterEntry, AgentMessage, AgentTask
)
from app.agents.events import (
    AgentCircuitBreakerTripped, AgentDeadLetterMessage, AgentTaskFailed
)


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_retries: int = 3,
        event_bus: Any = None
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._half_open_max_retries = half_open_max_retries
        self._event_bus = event_bus
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_retries = 0

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def name(self) -> str:
        return self._name

    def health(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "reset_timeout": self._reset_timeout
        }

    async def call(self, fn: Callable[[], Awaitable[Any]]) -> Any:
        if self._state == CircuitBreakerState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self._reset_timeout:
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_retries = 0
                logger.info(f"CircuitBreaker '{self._name}' transitioning to HALF_OPEN")
            else:
                raise RuntimeError(f"CircuitBreaker '{self._name}' is OPEN. Request rejected.")

        try:
            result = await fn()
            self._on_success()
            return result
        except Exception as e:
            await self._on_failure(str(e))
            raise

    def _on_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._half_open_retries += 1
            if self._half_open_retries >= self._half_open_max_retries:
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._half_open_retries = 0
                logger.info(f"CircuitBreaker '{self._name}' reset to CLOSED after successful retries.")
        else:
            self._failure_count = 0

    async def _on_failure(self, error: str) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._failure_threshold:
            self._state = CircuitBreakerState.OPEN
            logger.warning(f"CircuitBreaker '{self._name}' tripped to OPEN (failures={self._failure_count})")
            if self._event_bus:
                evt = AgentCircuitBreakerTripped(self._name, self._failure_count)
                try:
                    self._event_bus.publish_background(evt)
                except RuntimeError:
                    try:
                        asyncio.run(self._event_bus.publish(evt))
                    except Exception:
                        pass
                except Exception:
                    pass

    def reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_retries = 0
        logger.info(f"CircuitBreaker '{self._name}' manually reset to CLOSED.")


class RetryHandler:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        retryable_exceptions: Optional[List[type]] = None
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor
        self._retryable_exceptions = retryable_exceptions

    async def execute(
        self,
        fn: Callable[[], Awaitable[Any]],
        task: Optional[AgentTask] = None,
        event_bus: Any = None
    ) -> Any:
        last_exception: Optional[Exception] = None
        max_attempts = (task.max_retries if task and task.max_retries > 0 else self._max_retries) + 1

        for attempt in range(1, max_attempts + 1):
            try:
                return await fn()
            except Exception as e:
                last_exception = e
                if self._retryable_exceptions:
                    if not any(isinstance(e, exc) for exc in self._retryable_exceptions):
                        raise
                if attempt < max_attempts:
                    delay = min(self._base_delay * (self._backoff_factor ** (attempt - 1)), self._max_delay)
                    logger.warning(f"Retry attempt {attempt}/{max_attempts - 1} after {delay:.1f}s: {e}")
                    if event_bus and task:
                        evt = AgentTaskFailed(task.task_id, task.agent_id or "unknown", str(e))
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(event_bus.publish(evt))
                        except RuntimeError:
                            asyncio.run(event_bus.publish(evt))
                    await asyncio.sleep(delay)

        raise last_exception  # type: ignore


class DeadLetterQueue:
    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        self._entries: List[DeadLetterEntry] = []

    @property
    def entries(self) -> List[DeadLetterEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    async def put(self, message: AgentMessage, error: str) -> None:
        entry = DeadLetterEntry(
            message_id=message.message_id,
            original_message=message,
            error=error,
            retry_count=0,
            last_error=error
        )
        self._entries.append(entry)
        logger.warning(f"DeadLetterQueue: message {message.message_id} from {message.sender} queued. Error: {error}")
        if self._event_bus:
            evt = AgentDeadLetterMessage(message.message_id, error)
            try:
                self._event_bus.publish_background(evt)
            except RuntimeError:
                try:
                    asyncio.run(self._event_bus.publish(evt))
                except Exception:
                    pass

    async def retry(self, index: int = -1) -> Optional[AgentMessage]:
        if not self._entries:
            return None
        entry = self._entries.pop(index)
        entry.retry_count += 1
        logger.info(f"DeadLetterQueue: retrying message {entry.message_id} (attempt {entry.retry_count})")
        return entry.original_message

    async def retry_all(self) -> List[AgentMessage]:
        messages = [e.original_message for e in self._entries]
        self._entries.clear()
        logger.info(f"DeadLetterQueue: retrying all {len(messages)} messages.")
        return messages

    def clear(self) -> None:
        self._entries.clear()
        logger.info("DeadLetterQueue cleared.")

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "message": "DeadLetterQueue operational.",
            "details": {"queued_messages": self.count}
        }
