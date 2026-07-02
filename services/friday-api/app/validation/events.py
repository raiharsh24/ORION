from typing import Dict, Any, List, Optional
from app.events.events import FridayEvent


class ContextValidated(FridayEvent):
    def __init__(self, input_blocks: int, valid_blocks: int,
                 removed_duplicates: int, removed_invalid: int,
                 warnings: Optional[List[str]] = None) -> None:
        super().__init__(topic="ContextValidated", data={
            "input_blocks": input_blocks,
            "valid_blocks": valid_blocks,
            "removed_duplicates": removed_duplicates,
            "removed_invalid": removed_invalid,
            "warnings": warnings or [],
        })
