from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.extraction.base import ContextBlock


@dataclass
class RankedContextBlock:
    block: ContextBlock
    relevance_score: float = 0.0
    recency_score: float = 0.0
    importance_score: float = 0.0
    confidence_score: float = 0.0
    combined_score: float = 0.0


@dataclass
class RankingResult:
    ranked_blocks: List[RankedContextBlock] = field(default_factory=list)
    total_blocks: int = 0
    dropped_blocks: int = 0
    scores_summary: Optional[Dict[str, float]] = None


@dataclass
class RankingWeights:
    relevance_weight: float = 1.0
    recency_weight: float = 1.0
    importance_weight: float = 1.0
    confidence_weight: float = 1.0
    duplicate_penalty: float = 0.15
    pinned_boost: float = 0.5
    keyword_bonus: float = 0.25
    recency_halflife_hours: float = 24.0


DEFAULT_RANKING_WEIGHTS = RankingWeights()


class IContextRanker(ABC):

    @property
    @abstractmethod
    def ranker_name(self) -> str:
        ...

    @abstractmethod
    def rank(
        self,
        blocks: List[ContextBlock],
        query: str = "",
        weights: Optional[RankingWeights] = None,
    ) -> RankingResult:
        ...
