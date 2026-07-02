from typing import Dict, Any, List, Optional
from app.events.events import FridayEvent


class ContextRankingStarted(FridayEvent):
    def __init__(self, block_count: int, query: str = "", weights: Optional[Dict[str, float]] = None) -> None:
        super().__init__(topic="ContextRankingStarted", data={
            "block_count": block_count,
            "query": query,
            "weights": weights or {},
        })


class ContextRankingCompleted(FridayEvent):
    def __init__(self, block_count: int, dropped_blocks: int = 0,
                 scores_summary: Optional[Dict[str, float]] = None,
                 top_source: str = "") -> None:
        super().__init__(topic="ContextRankingCompleted", data={
            "block_count": block_count,
            "dropped_blocks": dropped_blocks,
            "scores_summary": scores_summary or {},
            "top_source": top_source,
        })
