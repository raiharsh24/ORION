import re
import math
from typing import List, Optional, Dict
from datetime import datetime, timezone
from loguru import logger

from app.extraction.base import ContextBlock
from app.ranking.base import (
    IContextRanker,
    RankedContextBlock,
    RankingResult,
    RankingWeights,
    DEFAULT_RANKING_WEIGHTS,
)
from app.ranking.events import ContextRankingStarted, ContextRankingCompleted
from app.events.bus import EventBus


class ContextRanker(IContextRanker):

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False

    @property
    def ranker_name(self) -> str:
        return "context_ranker"

    async def start(self) -> None:
        self._running = True
        logger.info("ContextRanker started.")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("ContextRanker shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "ranker_name": self.ranker_name,
                "running": self._running,
            },
        }

    def rank(
        self,
        blocks: List[ContextBlock],
        query: str = "",
        weights: Optional[RankingWeights] = None,
    ) -> RankingResult:
        if not blocks:
            return RankingResult(ranked_blocks=[], total_blocks=0, dropped_blocks=0)

        effective_weights = weights or DEFAULT_RANKING_WEIGHTS

        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    ContextRankingStarted(
                        block_count=len(blocks),
                        query=query,
                        weights={
                            "relevance_weight": effective_weights.relevance_weight,
                            "recency_weight": effective_weights.recency_weight,
                            "importance_weight": effective_weights.importance_weight,
                            "confidence_weight": effective_weights.confidence_weight,
                        },
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish ContextRankingStarted: {e}")

        query_tokens = self._tokenize(query) if query else []
        ranked: List[RankedContextBlock] = []

        seen_sources: Dict[str, int] = {}
        now = datetime.now(timezone.utc)

        for idx, block in enumerate(blocks):
            relevance_score = self._compute_relevance(block, query_tokens, effective_weights)
            recency_score = self._compute_recency(block, now, effective_weights)
            importance_score = self._clamp(block.importance, 0.0, 1.0)
            confidence_score = self._clamp(block.confidence, 0.0, 1.0)

            base_score = (
                relevance_score * effective_weights.relevance_weight
                + recency_score * effective_weights.recency_weight
                + importance_score * effective_weights.importance_weight
                + confidence_score * effective_weights.confidence_weight
            )

            source = block.source
            pinned = block.metadata.get("pinned", False) if block.metadata else False
            duplicate_penalty = 0.0
            pinned_bonus = 0.0

            if source:
                count = seen_sources.get(source, 0)
                if count > 0:
                    duplicate_penalty = effective_weights.duplicate_penalty * count
                seen_sources[source] = count + 1

            if pinned:
                pinned_bonus = effective_weights.pinned_boost

            combined_score = base_score - duplicate_penalty + pinned_bonus

            ranked.append(RankedContextBlock(
                block=block,
                relevance_score=relevance_score,
                recency_score=recency_score,
                importance_score=importance_score,
                confidence_score=confidence_score,
                combined_score=combined_score,
            ))

        ranked.sort(key=lambda rcb: -rcb.combined_score)

        total_scores = {
            "relevance": sum(r.relevance_score for r in ranked),
            "recency": sum(r.recency_score for r in ranked),
            "importance": sum(r.importance_score for r in ranked),
            "confidence": sum(r.confidence_score for r in ranked),
            "combined": sum(r.combined_score for r in ranked),
        }
        avg_scores = {k: round(v / len(ranked), 4) for k, v in total_scores.items()}

        top_source = ranked[0].block.source if ranked else ""

        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    ContextRankingCompleted(
                        block_count=len(ranked),
                        dropped_blocks=0,
                        scores_summary=avg_scores,
                        top_source=top_source,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish ContextRankingCompleted: {e}")

        return RankingResult(
            ranked_blocks=ranked,
            total_blocks=len(ranked),
            dropped_blocks=0,
            scores_summary=avg_scores,
        )

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "just", "because",
            "and", "but", "or", "if", "while", "about", "up",
        }
        return [t for t in tokens if t not in stop_words]

    @staticmethod
    def _compute_relevance(block: ContextBlock, query_tokens: List[str],
                           weights: RankingWeights) -> float:
        if not query_tokens:
            return 0.0

        block_tokens = set(
            ContextRanker._tokenize(block.title)
            + ContextRanker._tokenize(block.content)
            + ContextRanker._tokenize(block.source)
        )

        if not block_tokens:
            return 0.0

        matches = sum(1 for qt in query_tokens if qt in block_tokens)
        ratio = matches / len(query_tokens)

        if matches == 0:
            return 0.0
        return min(ratio + weights.keyword_bonus, 1.0)

    @staticmethod
    def _compute_recency(block: ContextBlock, now: datetime,
                         weights: RankingWeights) -> float:
        age_hours = (now - block.timestamp).total_seconds() / 3600.0
        halflife = weights.recency_halflife_hours
        if halflife <= 0:
            return 1.0
        return math.exp(-math.log(2) * age_hours / halflife)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
