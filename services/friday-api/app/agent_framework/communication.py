import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class AgentMessage:
    message_id: str = ""
    sender: str = ""
    recipient: str = ""
    message_type: str = "request"
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    timestamp: Optional[datetime] = None
    ttl_seconds: float = 30.0

    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)
        if not self.correlation_id:
            self.correlation_id = self.message_id


class CommunicationBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable[[AgentMessage], Awaitable[None]]]] = {}
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._message_history: List[AgentMessage] = []
        self._max_history = 1000

    def subscribe(self, agent_id: str,
                  handler: Callable[[AgentMessage], Awaitable[None]]) -> None:
        if agent_id not in self._handlers:
            self._handlers[agent_id] = []
        self._handlers[agent_id].append(handler)

    def unsubscribe(self, agent_id: str,
                    handler: Callable[[AgentMessage], Awaitable[None]]) -> bool:
        handlers = self._handlers.get(agent_id, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    async def send(self, message: AgentMessage) -> None:
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]

        if message.recipient == "*" or message.recipient == "broadcast":
            await self._broadcast(message)
        elif message.recipient in self._handlers:
            for handler in self._handlers[message.recipient]:
                await handler(message)

        if message.message_type == "response" and message.correlation_id in self._pending_responses:
            future = self._pending_responses.pop(message.correlation_id)
            if not future.done():
                future.set_result(message)

    async def _broadcast(self, message: AgentMessage) -> None:
        for agent_id, handlers in self._handlers.items():
            for handler in handlers:
                await handler(message)

    async def request(self, recipient: str, payload: Dict[str, Any],
                      sender: str = "", timeout: float = 30.0) -> Optional[AgentMessage]:
        correlation_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.Future()
        self._pending_responses[correlation_id] = future

        msg = AgentMessage(
            sender=sender,
            recipient=recipient,
            message_type="request",
            payload=payload,
            correlation_id=correlation_id,
            ttl_seconds=timeout,
        )

        await self.send(msg)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(correlation_id, None)
            return None

    async def respond(self, original: AgentMessage, payload: Dict[str, Any]) -> None:
        response = AgentMessage(
            sender=original.recipient,
            recipient=original.sender,
            message_type="response",
            payload=payload,
            correlation_id=original.correlation_id,
        )
        await self.send(response)

    async def broadcast(self, sender: str, payload: Dict[str, Any]) -> None:
        msg = AgentMessage(
            sender=sender,
            recipient="broadcast",
            message_type="broadcast",
            payload=payload,
        )
        await self.send(msg)

    def get_history(self, limit: int = 50) -> List[AgentMessage]:
        return self._message_history[-limit:]

    def clear_history(self) -> None:
        self._message_history.clear()

    def handler_count(self) -> int:
        return sum(len(h) for h in self._handlers.values())

    def health(self) -> dict:
        return {
            "subscribers": len(self._handlers),
            "handlers": self.handler_count(),
            "pending_responses": len(self._pending_responses),
            "history_size": len(self._message_history),
        }
