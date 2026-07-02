from typing import Dict, Any, Optional, List
from app.events.events import FridayEvent


STAGE_NAMES = [
    "intent_analysis",
    "strategy_resolution",
    "context_extraction",
    "context_ranking",
    "token_budget_allocation",
    "context_validation",
    "context_compression",
    "prompt_assembly",
]


class PipelineStarted(FridayEvent):
    def __init__(self, execution_id: str, request: str, session_id: str = "",
                 provider: str = "") -> None:
        super().__init__(topic="PipelineStarted", data={
            "execution_id": execution_id,
            "request": request,
            "session_id": session_id,
            "provider": provider,
        })


class PipelineStageStarted(FridayEvent):
    def __init__(self, execution_id: str, stage: str) -> None:
        super().__init__(topic="PipelineStageStarted", data={
            "execution_id": execution_id,
            "stage": stage,
        })


class PipelineStageCompleted(FridayEvent):
    def __init__(self, execution_id: str, stage: str, latency_ms: float = 0.0,
                 details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(topic="PipelineStageCompleted", data={
            "execution_id": execution_id,
            "stage": stage,
            "latency_ms": latency_ms,
            "details": details or {},
        })


class PipelineCompleted(FridayEvent):
    def __init__(self, execution_id: str, total_latency_ms: float = 0.0,
                 prompt_tokens: int = 0, status: str = "completed") -> None:
        super().__init__(topic="PipelineCompleted", data={
            "execution_id": execution_id,
            "total_latency_ms": total_latency_ms,
            "prompt_tokens": prompt_tokens,
            "status": status,
        })


class PipelineFailed(FridayEvent):
    def __init__(self, execution_id: str, stage: str = "", error: str = "",
                 total_latency_ms: float = 0.0) -> None:
        super().__init__(topic="PipelineFailed", data={
            "execution_id": execution_id,
            "stage": stage,
            "error": error,
            "total_latency_ms": total_latency_ms,
        })


class PipelineCancelled(FridayEvent):
    def __init__(self, execution_id: str, stage: str = "",
                 total_latency_ms: float = 0.0) -> None:
        super().__init__(topic="PipelineCancelled", data={
            "execution_id": execution_id,
            "stage": stage,
            "total_latency_ms": total_latency_ms,
        })


class StreamingStarted(FridayEvent):
    def __init__(self, execution_id: str, request: str, session_id: str = "") -> None:
        super().__init__(topic="StreamingStarted", data={
            "execution_id": execution_id,
            "request": request,
            "session_id": session_id,
        })


class ExtractorCompleted(FridayEvent):
    def __init__(self, execution_id: str, extractor_name: str, block_count: int,
                 latency_ms: float = 0.0) -> None:
        super().__init__(topic="ExtractorCompleted", data={
            "execution_id": execution_id,
            "extractor_name": extractor_name,
            "block_count": block_count,
            "latency_ms": latency_ms,
        })


class ContextUpdated(FridayEvent):
    def __init__(self, execution_id: str, total_blocks: int, estimated_tokens: int) -> None:
        super().__init__(topic="ContextUpdated", data={
            "execution_id": execution_id,
            "total_blocks": total_blocks,
            "estimated_tokens": estimated_tokens,
        })


class PromptUpdated(FridayEvent):
    def __init__(self, execution_id: str, prompt_tokens: int) -> None:
        super().__init__(topic="PromptUpdated", data={
            "execution_id": execution_id,
            "prompt_tokens": prompt_tokens,
        })


class StreamingCompleted(FridayEvent):
    def __init__(self, execution_id: str, total_latency_ms: float = 0.0,
                 final_prompt_tokens: int = 0) -> None:
        super().__init__(topic="StreamingCompleted", data={
            "execution_id": execution_id,
            "total_latency_ms": total_latency_ms,
            "final_prompt_tokens": final_prompt_tokens,
        })


class SnapshotLoaded(FridayEvent):
    def __init__(self, execution_id: str, session_id: str, snapshot_time: float) -> None:
        super().__init__(topic="SnapshotLoaded", data={
            "execution_id": execution_id,
            "session_id": session_id,
            "snapshot_time": snapshot_time,
        })


class ContextDeltaCalculated(FridayEvent):
    def __init__(self, execution_id: str, new_count: int, removed_count: int,
                 updated_count: int) -> None:
        super().__init__(topic="ContextDeltaCalculated", data={
            "execution_id": execution_id,
            "new_count": new_count,
            "removed_count": removed_count,
            "updated_count": updated_count,
        })


class SnapshotUpdated(FridayEvent):
    def __init__(self, execution_id: str, session_id: str, total_blocks: int) -> None:
        super().__init__(topic="SnapshotUpdated", data={
            "execution_id": execution_id,
            "session_id": session_id,
            "total_blocks": total_blocks,
        })


class IncrementalUpdateCompleted(FridayEvent):
    def __init__(self, execution_id: str, reused_count: int, recomputed_count: int,
                 speedup_ratio: float = 1.0) -> None:
        super().__init__(topic="IncrementalUpdateCompleted", data={
            "execution_id": execution_id,
            "reused_count": reused_count,
            "recomputed_count": recomputed_count,
            "speedup_ratio": speedup_ratio,
        })
