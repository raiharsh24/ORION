import math
from datetime import datetime, timezone, timedelta
from typing import List

import pytest

from app.extraction.base import ContextBlock
from app.ranking.base import (
    IContextRanker,
    RankedContextBlock,
    RankingResult,
    RankingWeights,
    DEFAULT_RANKING_WEIGHTS,
)
from app.ranking.ranker import ContextRanker
from app.ranking.events import ContextRankingStarted, ContextRankingCompleted


def make_block(
    source: str = "test",
    title: str = "",
    content: str = "",
    importance: float = 0.5,
    confidence: float = 1.0,
    timestamp: datetime = None,
    pinned: bool = False,
    estimated_tokens: int = 0,
) -> ContextBlock:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    meta = {}
    if pinned:
        meta["pinned"] = True
    return ContextBlock(
        source=source,
        title=title,
        content=content,
        importance=importance,
        confidence=confidence,
        timestamp=timestamp,
        metadata=meta,
        estimated_tokens=estimated_tokens,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ranker():
    return ContextRanker()


# ---------------------------------------------------------------------------
# Test: ContextRanker creation and naming
# ---------------------------------------------------------------------------

class TestContextRankerCreation:
    def test_ranker_name(self):
        r = ContextRanker()
        assert r.ranker_name == "context_ranker"

    def test_health_default(self):
        r = ContextRanker()
        h = r.health()
        assert h["status"] == "HEALTHY"
        assert h["details"]["ranker_name"] == "context_ranker"

    def test_start_shutdown(self):
        r = ContextRanker()
        assert not r._running
        import anyio
        anyio.run(r.start)
        assert r._running
        anyio.run(r.shutdown)
        assert not r._running

    def test_empty_blocks_returns_empty_result(self, ranker):
        result = ranker.rank([])
        assert result.ranked_blocks == []
        assert result.total_blocks == 0

    def test_single_block(self, ranker):
        block = make_block(source="mem", content="hello world")
        result = ranker.rank([block])
        assert len(result.ranked_blocks) == 1
        rc = result.ranked_blocks[0]
        assert rc.block is block

    def test_implements_interface(self):
        assert issubclass(ContextRanker, IContextRanker)
        r = ContextRanker()
        assert isinstance(r, IContextRanker)


# ---------------------------------------------------------------------------
# Test: RRIC scoring
# ---------------------------------------------------------------------------

class TestRRICScoring:

    def test_relevance_with_query_match(self, ranker):
        block = make_block(content="python code review")
        result = ranker.rank([block], query="python")
        assert result.ranked_blocks[0].relevance_score > 0

    def test_relevance_no_query(self, ranker):
        block = make_block(content="python code review")
        result = ranker.rank([block], query="")
        assert result.ranked_blocks[0].relevance_score == 0.0

    def test_relevance_no_match(self, ranker):
        block = make_block(content="python code review")
        result = ranker.rank([block], query="java")
        assert result.ranked_blocks[0].relevance_score == 0.0

    def test_relevance_title_match(self, ranker):
        block = make_block(title="deployment config", content="some content")
        result = ranker.rank([block], query="deployment")
        assert result.ranked_blocks[0].relevance_score > 0

    def test_recency_fresh_block(self, ranker):
        block = make_block(timestamp=datetime.now(timezone.utc))
        result = ranker.rank([block])
        assert result.ranked_blocks[0].recency_score == pytest.approx(1.0, rel=0.01)

    def test_recency_old_block(self, ranker):
        ts = datetime.now(timezone.utc) - timedelta(hours=48)
        block = make_block(timestamp=ts)
        result = ranker.rank([block])
        # With 24h halflife, 48h old = 0.25
        assert result.ranked_blocks[0].recency_score == pytest.approx(0.25, abs=0.01)

    def test_importance_score_from_block(self, ranker):
        block = make_block(importance=0.8)
        result = ranker.rank([block])
        assert result.ranked_blocks[0].importance_score == 0.8

    def test_confidence_score_from_block(self, ranker):
        block = make_block(confidence=0.7)
        result = ranker.rank([block])
        assert result.ranked_blocks[0].confidence_score == 0.7

    def test_importance_clamped(self, ranker):
        block = make_block(importance=1.5)
        result = ranker.rank([block])
        assert result.ranked_blocks[0].importance_score == 1.0

    def test_confidence_clamped(self, ranker):
        block = make_block(confidence=-0.5)
        result = ranker.rank([block])
        assert result.ranked_blocks[0].confidence_score == 0.0

    def test_combined_score_is_weighted_sum(self, ranker):
        w = RankingWeights(
            relevance_weight=1.0,
            recency_weight=0.5,
            importance_weight=2.0,
            confidence_weight=1.5,
            duplicate_penalty=0.0,
            pinned_boost=0.0,
            keyword_bonus=0.0,
            recency_halflife_hours=24.0,
        )
        block = make_block(importance=0.6, confidence=0.8)
        result = ranker.rank([block], query="", weights=w)
        rc = result.ranked_blocks[0]
        expected = 0.0 * 1.0 + 1.0 * 0.5 + 0.6 * 2.0 + 0.8 * 1.5
        assert rc.combined_score == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# Test: Deterministic ranking with stable sort
# ---------------------------------------------------------------------------

class TestDeterministicRanking:

    def test_equal_scores_preserve_insertion_order(self, ranker):
        same_ts = datetime.now(timezone.utc)
        blocks = [
            make_block(source="a", importance=0.5, confidence=1.0, timestamp=same_ts),
            make_block(source="b", importance=0.5, confidence=1.0, timestamp=same_ts),
            make_block(source="c", importance=0.5, confidence=1.0, timestamp=same_ts),
        ]
        result = ranker.rank(blocks, query="")
        sources = [rc.block.source for rc in result.ranked_blocks]
        assert sources == ["a", "b", "c"]

    def test_higher_combined_score_first(self, ranker):
        low = make_block(source="low", importance=0.1)
        high = make_block(source="high", importance=0.9)
        result = ranker.rank([low, high], query="")
        assert result.ranked_blocks[0].block.source == "high"
        assert result.ranked_blocks[1].block.source == "low"

    def test_ranking_reproducible(self, ranker):
        fixed_ts = datetime.now(timezone.utc)
        blocks = [
            make_block(source="x", importance=0.3, content="apple", timestamp=fixed_ts),
            make_block(source="y", importance=0.7, content="banana", timestamp=fixed_ts),
            make_block(source="z", importance=0.5, content="cherry", timestamp=fixed_ts),
        ]
        r1 = ranker.rank(blocks, query="test")
        r2 = ranker.rank(blocks, query="test")
        s1 = [rc.combined_score for rc in r1.ranked_blocks]
        s2 = [rc.combined_score for rc in r2.ranked_blocks]
        for a, b in zip(s1, s2):
            assert a == pytest.approx(b, abs=0.01)


# ---------------------------------------------------------------------------
# Test: Duplicate penalty
# ---------------------------------------------------------------------------

class TestDuplicateHandling:

    def test_duplicate_source_penalized(self, ranker):
        blocks = [
            make_block(source="mem", importance=0.5, content="first"),
            make_block(source="mem", importance=0.5, content="second"),
        ]
        result = ranker.rank(blocks, query="")
        assert result.ranked_blocks[0].combined_score > result.ranked_blocks[1].combined_score
        assert result.ranked_blocks[1].combined_score < result.ranked_blocks[0].combined_score

    def test_duplicate_penalty_increases_with_count(self, ranker):
        blocks = [
            make_block(source="mem", importance=0.5, content="first"),
            make_block(source="mem", importance=0.5, content="second"),
            make_block(source="mem", importance=0.5, content="third"),
        ]
        result = ranker.rank(blocks, query="")
        # first > second > third due to increasing penalty
        scores = [rc.combined_score for rc in result.ranked_blocks]
        assert scores[0] > scores[1] > scores[2]

    def test_no_penalty_for_distinct_sources(self, ranker):
        same_ts = datetime.now(timezone.utc)
        blocks = [
            make_block(source="mem", importance=0.5, timestamp=same_ts),
            make_block(source="kb", importance=0.5, timestamp=same_ts),
            make_block(source="web", importance=0.5, timestamp=same_ts),
        ]
        result = ranker.rank(blocks, query="")
        scores = [rc.combined_score for rc in result.ranked_blocks]
        assert scores[0] == scores[1] == scores[2]


# ---------------------------------------------------------------------------
# Test: Timestamp decay
# ---------------------------------------------------------------------------

class TestTimestampDecay:

    def test_newer_block_ranks_higher(self, ranker):
        now = datetime.now(timezone.utc)
        old = make_block(source="old", timestamp=now - timedelta(hours=72), importance=0.5)
        new = make_block(source="new", timestamp=now, importance=0.5)
        result = ranker.rank([old, new], query="")
        assert result.ranked_blocks[0].block.source == "new"
        assert result.ranked_blocks[1].block.source == "old"

    def test_custom_halflife(self, ranker):
        w = DEFAULT_RANKING_WEIGHTS
        w = RankingWeights(recency_halflife_hours=1.0)
        now = datetime.now(timezone.utc)
        old = make_block(source="old", timestamp=now - timedelta(hours=2), importance=0.5)
        new = make_block(source="new", timestamp=now, importance=0.5)
        result = ranker.rank([old, new], query="", weights=w)
        # With 1h halflife, old has decayed to 0.25 while new is 1.0
        assert result.ranked_blocks[0].block.source == "new"

    def test_zero_halflife_returns_1(self, ranker):
        w = RankingWeights(recency_halflife_hours=0.0)
        block = make_block(timestamp=datetime.now(timezone.utc) - timedelta(hours=999))
        result = ranker.rank([block], query="", weights=w)
        assert result.ranked_blocks[0].recency_score == 1.0


# ---------------------------------------------------------------------------
# Test: User-pinned context boost
# ---------------------------------------------------------------------------

class TestPinnedBoost:

    def test_pinned_block_boosted(self, ranker):
        blocks = [
            make_block(source="a", importance=0.5, pinned=False),
            make_block(source="b", importance=0.5, pinned=True),
        ]
        result = ranker.rank(blocks, query="")
        assert result.ranked_blocks[0].block.source == "b"

    def test_pinned_boost_value(self, ranker):
        w = RankingWeights(pinned_boost=1.0, duplicate_penalty=0.0, keyword_bonus=0.0)
        block = make_block(source="pinned", importance=0.5, pinned=True)
        result = ranker.rank([block], query="", weights=w)
        base = 0.0 + 1.0 + 0.5 + 1.0
        expected = base + 1.0
        assert result.ranked_blocks[0].combined_score == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# Test: Keyword bonus in relevance
# ---------------------------------------------------------------------------

class TestKeywordBonus:

    def test_keyword_bonus_applied(self, ranker):
        w = RankingWeights(keyword_bonus=0.5, duplicate_penalty=0.0, pinned_boost=0.0)
        block = make_block(content="python deployment")
        result = ranker.rank([block], query="python", weights=w)
        # baseline match ratio = 1/1 = 1.0, + bonus 0.5 => capped to 1.0
        assert result.ranked_blocks[0].relevance_score == 1.0

    def test_no_keyword_bonus_when_zero(self, ranker):
        w = RankingWeights(keyword_bonus=0.0, duplicate_penalty=0.0, pinned_boost=0.0)
        block = make_block(content="python deployment")
        result = ranker.rank([block], query="python", weights=w)
        # match ratio = 1.0, no bonus
        assert result.ranked_blocks[0].relevance_score == 1.0


# ---------------------------------------------------------------------------
# Test: Weights configurability
# ---------------------------------------------------------------------------

class TestWeightConfigurability:

    def test_custom_weights_affect_scores(self, ranker):
        w_default = DEFAULT_RANKING_WEIGHTS
        w_custom = RankingWeights(
            relevance_weight=5.0,
            recency_weight=0.0,
            importance_weight=0.0,
            confidence_weight=0.0,
        )
        block = make_block(content="api endpoint", importance=0.2)
        r_default = ranker.rank([block], query="api", weights=w_default)
        r_custom = ranker.rank([block], query="api", weights=w_custom)
        # With 5x relevance weight, custom combined should be higher
        assert r_custom.ranked_blocks[0].combined_score > r_default.ranked_blocks[0].combined_score

    def test_weights_not_mutated(self, ranker):
        w = RankingWeights()
        original = w.relevance_weight
        block = make_block(content="test")
        ranker.rank([block], query="test", weights=w)
        assert w.relevance_weight == original


# ---------------------------------------------------------------------------
# Test: RankingResult structure
# ---------------------------------------------------------------------------

class TestRankingResultStructure:

    def test_result_has_all_fields(self, ranker):
        block = make_block(content="hello")
        result = ranker.rank([block], query="hello")
        assert hasattr(result, "ranked_blocks")
        assert hasattr(result, "total_blocks")
        assert hasattr(result, "dropped_blocks")
        assert hasattr(result, "scores_summary")

    def test_scores_summary_has_averages(self, ranker):
        blocks = [
            make_block(content="python", importance=0.5),
            make_block(content="java", importance=0.8),
        ]
        result = ranker.rank(blocks, query="python")
        assert "relevance" in result.scores_summary
        assert "recency" in result.scores_summary
        assert "importance" in result.scores_summary
        assert "confidence" in result.scores_summary
        assert "combined" in result.scores_summary

    def test_total_blocks_matches_input(self, ranker):
        blocks = [make_block() for _ in range(5)]
        result = ranker.rank(blocks, query="")
        assert result.total_blocks == 5


# ---------------------------------------------------------------------------
# Test: Stress / performance
# ---------------------------------------------------------------------------

class TestStress:

    def test_100_blocks_ranks_quickly(self, ranker):
        blocks = [
            make_block(
                source=f"src{i % 5}",
                content=f"content block number {i}",
                importance=(i % 10) / 10.0,
                confidence=(i % 5 + 1) / 5.0,
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i),
            )
            for i in range(100)
        ]
        import time
        start = time.perf_counter()
        result = ranker.rank(blocks, query="content block")
        elapsed = time.perf_counter() - start
        assert len(result.ranked_blocks) == 100
        assert elapsed < 2.0

    def test_1000_blocks_no_error(self, ranker):
        blocks = [
            make_block(
                source=f"src{i % 20}",
                content=f"block {i}",
                importance=0.5,
            )
            for i in range(1000)
        ]
        result = ranker.rank(blocks, query="block")
        assert len(result.ranked_blocks) == 1000


# ---------------------------------------------------------------------------
# Test: Event publishing (integration-lite)
# ---------------------------------------------------------------------------

class TestEventPublishing:

    @pytest.mark.anyio
    async def test_rank_publishes_events(self):
        from app.events.bus import EventBus

        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("ContextRankingStarted", capture)
        bus.subscribe("ContextRankingCompleted", capture)

        ranker = ContextRanker(event_bus=bus)
        await ranker.start()

        block = make_block(content="test event")
        ranker.rank([block], query="test")

        await bus.shutdown()

        assert "ContextRankingStarted" in received
        assert "ContextRankingCompleted" in received

    @pytest.mark.anyio
    async def test_rank_no_events_when_not_running(self):
        from app.events.bus import EventBus

        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("ContextRankingStarted", capture)
        bus.subscribe("ContextRankingCompleted", capture)

        ranker = ContextRanker(event_bus=bus)
        block = make_block(content="test")
        ranker.rank([block], query="test")

        await bus.shutdown()

        assert "ContextRankingStarted" not in received
        assert "ContextRankingCompleted" not in received


# ---------------------------------------------------------------------------
# Test: Kernel integration
# ---------------------------------------------------------------------------

class TestKernelIntegration:

    @pytest.mark.anyio
    async def test_kernel_boot_includes_context_ranker(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        from app.ranking.ranker import ContextRanker

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("context_ranker")
            assert svc is not None
            assert isinstance(svc, ContextRanker)

            h = kernel.health()
            assert h.context_ranker.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_lifecycle_via_kernel(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        from app.ranking.ranker import ContextRanker

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            ranker = kernel.get_service("context_ranker")
            assert ranker is not None
            assert ranker._running

            block = make_block(content="kernel integration test")
            result = ranker.rank([block], query="kernel")
            assert len(result.ranked_blocks) == 1
            assert result.ranked_blocks[0].relevance_score > 0
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_kernel_restart(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()
        await kernel.shutdown()
        await kernel.boot()

        try:
            ranker = kernel.get_service("context_ranker")
            assert ranker is not None
            assert ranker._running
            h = kernel.health()
            assert h.context_ranker.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_regression_kernel_boot_other_subsystems_unaffected(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            assert kernel.get_service("intent_analyzer") is not None
            assert kernel.get_service("strategy_manager") is not None
            assert kernel.get_service("extractor_registry") is not None
            assert kernel.get_service("context_ranker") is not None
            assert kernel.get_service("event_bus") is not None
        finally:
            await kernel.shutdown()


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_block_missing_timestamp(self, ranker):
        block = ContextBlock(
            source="test",
            title="no timestamp",
            content="content",
        )
        result = ranker.rank([block])
        assert len(result.ranked_blocks) == 1

    def test_all_zero_weights(self, ranker):
        w = RankingWeights(
            relevance_weight=0.0,
            recency_weight=0.0,
            importance_weight=0.0,
            confidence_weight=0.0,
            duplicate_penalty=0.0,
            pinned_boost=0.0,
            keyword_bonus=0.0,
        )
        blocks = [
            make_block(source="a", importance=1.0),
            make_block(source="b", importance=0.0),
        ]
        result = ranker.rank(blocks, query="", weights=w)
        assert all(rc.combined_score == 0.0 for rc in result.ranked_blocks)

    def test_long_query_relevance(self, ranker):
        block = make_block(content="the quick brown fox jumps over the lazy dog")
        result = ranker.rank([block], query="fox dog")
        assert result.ranked_blocks[0].relevance_score > 0

    def test_stop_words_in_query_filtered(self, ranker):
        block = make_block(content="python programming")
        result = ranker.rank([block], query="the python and programming")
        # "the" and "and" are stop words, "python" and "programming" match
        assert result.ranked_blocks[0].relevance_score > 0

    def test_negative_importance_clamped(self, ranker):
        block = make_block(importance=-1.0)
        result = ranker.rank([block])
        assert result.ranked_blocks[0].importance_score == 0.0

    def test_negative_confidence_clamped(self, ranker):
        block = make_block(confidence=-1.0)
        result = ranker.rank([block])
        assert result.ranked_blocks[0].confidence_score == 0.0

    def test_block_with_empty_strings(self, ranker):
        block = ContextBlock(source="", title="", content="", importance=0.5, confidence=0.5)
        result = ranker.rank([block])
        assert len(result.ranked_blocks) == 1
        assert result.ranked_blocks[0].relevance_score == 0.0


# ---------------------------------------------------------------------------
# Test: Regression - ranking consistency with prior extraction result
# ---------------------------------------------------------------------------

class TestRegression:

    def test_rank_from_extraction_result(self, ranker):
        from app.extraction.base import ExtractionResult

        blocks = [
            make_block(source="mem", content="previous session data", importance=0.7),
            make_block(source="kb", content="project documentation", importance=0.4),
        ]
        extraction = ExtractionResult(blocks=blocks)
        result = ranker.rank(extraction.blocks, query="session")
        assert len(result.ranked_blocks) == 2
        assert result.ranked_blocks[0].block.source == "mem"

    def test_duplicate_and_pinned_interaction(self, ranker):
        w = RankingWeights(duplicate_penalty=0.5, pinned_boost=1.0)
        blocks = [
            make_block(source="mem", importance=0.5, content="first"),
            make_block(source="mem", importance=0.5, content="second", pinned=True),
        ]
        result = ranker.rank(blocks, query="", weights=w)
        # pinned block gets +1.0 boost, duplicate applies -0.5 penalty; net +0.5
        assert result.ranked_blocks[0].block.metadata.get("pinned") is True
        assert result.ranked_blocks[0].relevance_score == 0.0
        assert result.ranked_blocks[1].block.metadata.get("pinned") is not True
