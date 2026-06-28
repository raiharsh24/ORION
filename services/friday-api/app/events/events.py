import time
from typing import Dict, Any

class FridayEvent:
    """
    Data payload container for system event broadcasts.

    TODO:
    - Include serialized schemas
    - Validate event payload parameters
    """
    def __init__(self, topic: str, data: Dict[str, Any]) -> None:
        self.topic = topic
        self.data = data
        self.timestamp: float = time.time()
