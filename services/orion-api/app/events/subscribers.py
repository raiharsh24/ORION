from typing import Callable, Any
from app.events.events import OrionEvent

class EventSubscriber:
    """
    Subscribes callbacks to designated EventBus channels.

    TODO:
    - Listen for specific system events
    - Register callbacks dynamically
    """
    def __init__(self, topic: str, handler: Callable[[OrionEvent], Any]) -> None:
        self.topic = topic
        self.handler = handler

    async def on_event(self, event: OrionEvent) -> None:
        """
        Triggers handler logic upon topic matches.

        Args:
            event (OrionEvent): Matched event details.
        """
        # TODO: Implement callback trigger pipeline
        pass
