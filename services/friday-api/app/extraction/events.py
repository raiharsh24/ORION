from typing import Dict, Any, List, Optional
from app.events.events import FridayEvent


class ContextExtractionStarted(FridayEvent):
    def __init__(self, request: str, extractor_names: List[str], strategy_name: str = "") -> None:
        super().__init__(topic="ContextExtractionStarted", data={
            "request": request,
            "extractor_names": extractor_names,
            "strategy_name": strategy_name,
        })


class ContextExtractionCompleted(FridayEvent):
    def __init__(self, request: str = "", block_count: int = 0,
                 total_tokens: int = 0, partial_failures: Optional[List[str]] = None) -> None:
        super().__init__(topic="ContextExtractionCompleted", data={
            "request": request,
            "block_count": block_count,
            "total_tokens": total_tokens,
            "partial_failures": partial_failures or [],
        })


class ContextExtractionFailed(FridayEvent):
    def __init__(self, request: str = "", error: str = "",
                 extractor_name: str = "") -> None:
        super().__init__(topic="ContextExtractionFailed", data={
            "request": request,
            "error": error,
            "extractor_name": extractor_name,
        })
