import uuid
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from loguru import logger

from app.agents.models import AgentMessage
from app.agents.events import AgentMessageSent, AgentMessageReceived, AgentError
from app.events.events import FridayEvent


class AgentMessageBus:
    def __init__(self, event_bus: Any) -> None:
        self._event_bus = event_bus
        self._handlers: Dict[str, List[Callable[[AgentMessage], Any]]] = {}
        self._pending_responses: Dict[str, asyncio.Future] = {}

    @property
    def event_bus(self) -> Any:
        return self._event_bus

    async def send(self, message: AgentMessage) -> None:
        logger.debug(f"AgentMessageBus: sending msg {message.message_id} "
                      f"from {message.sender} to {message.recipient or '*'}")

        self._event_bus and self._event_bus.publish_background(AgentMessageSent(
            message.message_id, message.sender,
            message.recipient or "*", message.type
        ))

        if message.recipient and message.recipient != "*":
            handlers = self._handlers.get(message.recipient, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    logger.error(f"Handler for {message.recipient} failed: {e}")
                    self._event_bus and self._event_bus.publish_background(AgentError(message.sender, str(e)))
            self._event_bus and self._event_bus.publish_background(AgentMessageReceived(
                message.message_id, message.recipient, message.sender, message.type
            ))
        else:
            for agent_id, handlers in self._handlers.items():
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Broadcast handler for {agent_id} failed: {e}")
            self._event_bus and self._event_bus.publish_background(AgentMessageReceived(
                message.message_id, "*", message.sender, message.type
            ))

        if (message.type == "RESPONSE"
                and message.correlation_id
                and message.correlation_id in self._pending_responses):
            future = self._pending_responses.pop(message.correlation_id)
            if not future.done():
                future.set_result(message)

    async def publish(self, topic: str, message: AgentMessage) -> None:
        message.type = "EVENT"
        evt = FridayEvent(topic, message.model_dump())
        await self._event_bus.publish(evt)

    async def request(
        self,
        recipient: str,
        message: AgentMessage,
        timeout: float = 30.0
    ) -> Optional[AgentMessage]:
        correlation_id = message.correlation_id or message.message_id
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = future

        message.type = "REQUEST"
        message.correlation_id = correlation_id
        await self.send(message)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(correlation_id, None)
            logger.warning(f"Request to {recipient} timed out after {timeout}s")
            return None

    async def broadcast(self, message: AgentMessage) -> None:
        message.recipient = None
        message.type = "BROADCAST"
        await self.send(message)

    def respond(self, request: AgentMessage, response_payload: Dict[str, Any]) -> AgentMessage:
        return AgentMessage(
            message_id=uuid.uuid4().hex,
            sender=request.recipient or "system",
            recipient=request.sender,
            type="RESPONSE",
            payload=response_payload,
            correlation_id=request.correlation_id
        )

    def subscribe(self, agent_id: str, handler: Callable[[AgentMessage], Any]) -> None:
        if agent_id not in self._handlers:
            self._handlers[agent_id] = []
        self._handlers[agent_id].append(handler)
        logger.debug(f"AgentMessageBus: subscribed {agent_id}")

    def unsubscribe(self, agent_id: str, handler: Callable[[AgentMessage], Any]) -> None:
        if agent_id in self._handlers:
            self._handlers[agent_id] = [h for h in self._handlers[agent_id] if h != handler]



    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "message": "AgentMessageBus operational.",
            "details": {
                "subscribers": len(self._handlers),
                "pending_responses": len(self._pending_responses)
            }
        }
