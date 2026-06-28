import inspect
import re
import asyncio
from typing import Dict, List, Callable, Any, Optional, Set
from loguru import logger
from app.events.events import OrionEvent

class EventBus:
    """
    Centralized event communication bus supporting async handlers, wildcard topics,
    prioritized execution, and pre-dispatch middleware interceptors.
    """
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[tuple[Callable[[OrionEvent], Any], int]]] = {}
        self._middlewares: List[Callable[[OrionEvent], Optional[OrionEvent]]] = []
        self._background_tasks: Set[asyncio.Task] = set()

    def add_middleware(self, middleware: Callable[[OrionEvent], Optional[OrionEvent]]) -> None:
        """
        Registers middleware interceptor. Called before dispatching.
        If middleware returns None, the event is dropped.
        """
        self._middlewares.append(middleware)

    def subscribe(self, event_type: str, callback: Callable[[OrionEvent], Any], priority: int = 100) -> None:
        """
        Subscribes to an event pattern.
        
        Args:
            event_type: Event name or wildcard pattern (e.g. 'conversation.*' or '*').
            callback: Coroutine or synchronous function.
            priority: Lower integers run first (e.g. 0 before 100).
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append((callback, priority))
        # Keep sorted by priority
        self._subscribers[event_type].sort(key=lambda x: x[1])
        logger.debug(f"Subscribed {callback.__name__ if hasattr(callback, '__name__') else 'handler'} to '{event_type}' (priority={priority})")

    def unsubscribe(self, event_type: str, callback: Callable[[OrionEvent], Any]) -> None:
        """Unsubscribes a subscriber from a pattern."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                item for item in self._subscribers[event_type] if item[0] != callback
            ]

    def _matches(self, pattern: str, topic: str) -> bool:
        """Evaluates pattern matching for wildcard subscribers."""
        if pattern == "*" or pattern == "#":
            return True
        # Simple glob to regex
        regex_pattern = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
        return bool(re.match(regex_pattern, topic))

    async def publish(self, event: OrionEvent) -> None:
        """
        Publishes an event asynchronously, pushing it through registered middlewares and dispatching
        it to all matching subscribers grouped by priority. Within each priority group, handlers
        execute concurrently via asyncio.gather. Priority groups execute in order (lowest first).
        """
        # Execute middleware interceptors
        current_event = event
        for middleware in self._middlewares:
            try:
                if inspect.iscoroutinefunction(middleware):
                    res = await middleware(current_event)
                else:
                    res = middleware(current_event)
                if res is None:
                    logger.debug(f"Event '{event.topic}' cancelled by middleware.")
                    return
                current_event = res
            except Exception as e:
                logger.error(f"EventBus middleware processing failed for topic '{event.topic}': {str(e)}")
                return

        # Consolidate all subscribers matching the published topic pattern
        matching_handlers: List[tuple[Callable[[OrionEvent], Any], int]] = []
        for pattern, subscribers in self._subscribers.items():
            if self._matches(pattern, current_event.topic):
                matching_handlers.extend(subscribers)

        # Sort matched subscribers by priority
        matching_handlers.sort(key=lambda x: x[1])

        # Group by priority for ordered concurrent dispatch
        groups: Dict[int, List[Callable[[OrionEvent], Any]]] = {}
        for callback, priority in matching_handlers:
            groups.setdefault(priority, []).append(callback)

        # Execute each priority group sequentially, handlers within group concurrently
        for priority in sorted(groups.keys()):
            handlers = groups[priority]
            coros = []
            for callback in handlers:
                if inspect.iscoroutinefunction(callback):
                    coros.append(callback(current_event))
                else:
                    coros.append(asyncio.to_thread(callback, current_event))
            results = await asyncio.gather(*coros, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in EventBus subscriber on topic '{current_event.topic}': {result}")

    def publish_background(self, event: OrionEvent) -> None:
        """Fire-and-forget event publication in a supervised background task."""
        task = asyncio.create_task(self._background_publish(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _background_publish(self, event: OrionEvent) -> None:
        try:
            await self.publish(event)
        except Exception as e:
            logger.error(f"Background event failed for topic '{event.topic}': {e}")

    async def shutdown(self) -> None:
        """Wait for all pending background tasks to complete."""
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
