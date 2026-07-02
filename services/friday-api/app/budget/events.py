from typing import Dict, Any, Optional
from app.events.events import FridayEvent


class TokenBudgetAllocated(FridayEvent):
    def __init__(self, total_budget: int, allocated_tokens: int,
                 selected_blocks: int, discarded_blocks: int,
                 utilization_percentage: float, model_name: str = "") -> None:
        super().__init__(topic="TokenBudgetAllocated", data={
            "total_budget": total_budget,
            "allocated_tokens": allocated_tokens,
            "selected_blocks": selected_blocks,
            "discarded_blocks": discarded_blocks,
            "utilization_percentage": utilization_percentage,
            "model_name": model_name,
        })
