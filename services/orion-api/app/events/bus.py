from typing import Dict, List, Callable, Any
from app.events.events import OrionEvent

class EventBus:
    """
    Decoupled publish/subscribe event communication gateway.

    TODO:
    - Support event mapping registration queries
    - Dispatch events to thread/asynchronous workers
    - Safely intercept errors within subscriber callbacks
    """
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[OrionEvent], Any]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[OrionEvent], Any]) -> None:
        """
        Registers a callback subscriber.

        Args:
            event_type (str): Event identifier topic.
            callback (Callable): Callback function wrapper.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[OrionEvent], Any]) -> None:
        """
        Removes a callback subscriber.

        Args:
            event_type (str): Event identifier topic.
            callback (Callable): Callback function wrapper to remove.
        """
        if event_type in self._subscribers and callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    async def publish(self, event: OrionEvent) -> None:
        """
        Dispatches an event payload to matching subscribers.

        Args:
            event (OrionEvent): Dispatched event details.
        """
        topic = event.topic
        subscribers = self._subscribers.get(topic, [])
        for callback in list(subscribers):
            try:
                import inspect
                if inspect.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                from loguru import logger
                logger.error(f"Error in subscriber callback for {topic}: {str(e)}")

        wildcard_subs = self._subscribers.get("*", [])
        for callback in list(wildcard_subs):
            try:
                import inspect
                if inspect.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                from loguru import logger
                logger.error(f"Error in wildcard subscriber callback for {topic}: {str(e)}")
