import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.cache.base import CacheKey, CacheLevel, compute_context_hash
from app.cache.cache import ContextCache
from app.events.bus import EventBus
from app.extraction.base import ContextBlock, ExtractionResult
from app.ranking.base import RankingResult, RankedContextBlock
from app.compression.base import CompressionResult, CompressedBlock
from app.assembly.base import PromptFrame
from app.intent.analyzer import IntentResult
from app.intent.types import IntentType
from app.context.base import StrategyConfig

from app.intelligence.streaming import (
    StreamingPipeline,
    StreamingContextBuilder,
    PipelineBarrier,
    PipelineScheduler,
    StreamingMetrics,
    StreamingResult,
)


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def cache(event_bus):
    return ContextCache(event_bus=event_bus, cleanup_interval=0.1)


@pytest.mark.anyio
async def test_pipeline_barrier():
    barrier = PipelineBarrier(["extractor1", "extractor2"])
    assert not barrier.is_done()

    barrier.complete("extractor1", [ContextBlock(source="test", content="c1")], 15.0)
    assert not barrier.is_done()

    ext_name, blocks, latency = await barrier.queue.get()
    assert ext_name == "extractor1"
    assert len(blocks) == 1
    assert latency == 15.0

    barrier.complete("extractor2", [], 5.0)
    assert barrier.is_done()


@pytest.mark.anyio
async def test_pipeline_scheduler():
    barrier = PipelineBarrier(["fast", "slow"])
    
    mock_fast = AsyncMock()
    mock_fast.extract.return_value = [ContextBlock(source="fast", content="fast_content")]
    
    mock_slow = AsyncMock()
    async def slow_extract(req):
        await asyncio.sleep(0.1)
        return [ContextBlock(source="slow", content="slow_content")]
    mock_slow.extract.side_effect = slow_extract

    mock_registry = MagicMock()
    mock_registry.get.side_effect = lambda name: mock_fast if name == "fast" else mock_slow

    scheduler = PipelineScheduler(mock_registry, barrier, timeout=0.2)
    scheduler.start_extraction("test query", ["fast", "slow"])

    # Wait for fast to complete
    ext_name1, blocks1, lat1 = await barrier.queue.get()
    assert ext_name1 == "fast"
    assert len(blocks1) == 1

    # Wait for slow to complete
    ext_name2, blocks2, lat2 = await barrier.queue.get()
    assert ext_name2 == "slow"
    assert len(blocks2) == 1
    assert barrier.is_done()


@pytest.mark.anyio
async def test_stream_ordering_and_deterministic_growth():
    # Verify that already accepted blocks are never reordered.
    mock_ranker = MagicMock()
    # Ranker returns ranking results in order of input blocks
    def mock_rank(blocks, query):
        rbs = []
        for b in blocks:
            score = 0.9 if b.source == "high" else 0.4
            rbs.append(RankedContextBlock(block=b, relevance_score=score, combined_score=score))
        return RankingResult(ranked_blocks=rbs)
    mock_ranker.rank.side_effect = mock_rank

    mock_alloc = MagicMock()
    mock_alloc.allocate.side_effect = lambda rbs, config, strategy: type("AllocRes", (), {
        "selected_blocks": rbs,
        "report": None
    })()

    mock_val = MagicMock()
    mock_val.validate.side_effect = lambda sbs, strategy: type("ValRes", (), {
        "valid_blocks": sbs,
        "report": None
    })()

    mock_comp = MagicMock()
    mock_comp.compress.side_effect = lambda vbs, policy, strategy: CompressionResult(
        compressed_blocks=[CompressedBlock(block=type("AllocBlk", (), {"block": b})()) for b in vbs]
    )

    mock_asms = MagicMock()
    # Assembler combines content
    def mock_assemble(cbs, compression_report, budget_report, strategy, provider):
        contents = [cb.block.block.block.content for cb in cbs]
        text = " -> ".join(contents)
        report = type("AsmRep", (), {"prompt_tokens": len(text)})()
        frame = PromptFrame(text_prompt=text)
        return type("AsmRes", (), {"frame": frame, "report": report})()
    mock_asms.assemble.side_effect = mock_assemble

    sc = StrategyConfig(extractors=["e1", "e2"])
    metrics = StreamingMetrics()

    builder = StreamingContextBuilder(
        query="test query",
        strategy_config=sc,
        token_allocator=mock_alloc,
        context_validator=mock_val,
        context_compressor=mock_comp,
        prompt_assembler=mock_asms,
        context_ranker=mock_ranker,
        metrics=metrics,
        insertion_threshold=0.5,
    )

    # First completed extractor (low score block)
    b_low = ContextBlock(source="low", content="Low priority content")
    builder.add_blocks([b_low])
    assert builder.prompt_frame.text_prompt == "Low priority content"

    # Late completed extractor (high score block)
    b_high = ContextBlock(source="high", content="High priority content")
    builder.add_blocks([b_high])

    # The high priority content is appended and NOT reordered to the front
    assert builder.prompt_frame.text_prompt == "Low priority content -> High priority content"


@pytest.mark.anyio
async def test_late_extractor_threshold_and_budget():
    # If budget is full, block is only accepted if score exceeds insertion threshold
    mock_ranker = MagicMock()
    def mock_rank(blocks, query):
        rbs = []
        for b in blocks:
            score = 0.8 if b.source == "strong" else 0.3
            rbs.append(RankedContextBlock(block=b, relevance_score=score, combined_score=score))
        return RankingResult(ranked_blocks=rbs)
    mock_ranker.rank.side_effect = mock_rank

    mock_alloc = MagicMock()
    mock_alloc.allocate.side_effect = lambda rbs, config, strategy: type("AllocRes", (), {"selected_blocks": rbs, "report": None})()
    mock_val = MagicMock()
    mock_val.validate.side_effect = lambda sbs, strategy: type("ValRes", (), {"valid_blocks": sbs, "report": None})()
    mock_comp = MagicMock()
    mock_comp.compress.side_effect = lambda vbs, policy, strategy: CompressionResult(
        compressed_blocks=[CompressedBlock(block=type("AllocBlk", (), {"block": b})()) for b in vbs]
    )
    mock_asms = MagicMock()
    mock_asms.assemble.side_effect = lambda compressed_blocks, compression_report=None, budget_report=None, strategy=None, provider="gemini": type("AsmRes", (), {
        "frame": PromptFrame(text_prompt="ok"),
        "report": type("AsmRep", (), {"prompt_tokens": 10})()
    })()

    # Small budget
    sc = StrategyConfig(extractors=["e1", "e2"])
    sc.token_budget = MagicMock()
    sc.token_budget.total = 15

    metrics = StreamingMetrics()
    builder = StreamingContextBuilder(
        query="test query",
        strategy_config=sc,
        token_allocator=mock_alloc,
        context_validator=mock_val,
        context_compressor=mock_comp,
        prompt_assembler=mock_asms,
        context_ranker=mock_ranker,
        metrics=metrics,
        insertion_threshold=0.6,
    )

    # Initial block takes 10 tokens (less than 15, remaining budget > 0)
    b1 = ContextBlock(source="weak", content="weak content", estimated_tokens=10)
    builder.add_blocks([b1])
    assert len(builder.accepted_blocks) == 1

    # Late block: weak score (0.3), no remaining budget (10/15 filled, but wait: 10 + 10 = 20 > 15).
    # Since budget limit is 15, and current tokens is 10, remaining budget is 5 (> 0).
    # Wait, let's see. If remaining budget is > 0, does it accept?
    # Yes, remaining budget (15 - 10 = 5) is > 0, so weak block is accepted.
    b2 = ContextBlock(source="weak", content="another weak", estimated_tokens=10)
    builder.add_blocks([b2])
    assert len(builder.accepted_blocks) == 2

    # Now total tokens is 20, remaining budget is -5 (<= 0).
    # Next weak block should be rejected because score (0.3) < threshold (0.6).
    b3 = ContextBlock(source="weak", content="rejected weak", estimated_tokens=5)
    builder.add_blocks([b3])
    assert len(builder.accepted_blocks) == 2

    # Next strong block should be accepted because score (0.8) >= threshold (0.6)
    b4 = ContextBlock(source="strong", content="accepted strong", estimated_tokens=5)
    builder.add_blocks([b4])
    assert len(builder.accepted_blocks) == 3
    assert builder.accepted_blocks[-1].block.source == "strong"


@pytest.mark.anyio
async def test_scheduler_timeout():
    barrier = PipelineBarrier(["slow"])
    mock_slow = AsyncMock()
    async def slow_extract(req):
        await asyncio.sleep(0.3)
        return [ContextBlock(source="slow", content="slow_content")]
    mock_slow.extract.side_effect = slow_extract

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_slow

    scheduler = PipelineScheduler(mock_registry, barrier, timeout=0.05)
    scheduler.start_extraction("test", ["slow"])

    # Wait for completion (should timeout and return empty blocks)
    ext_name, blocks, latency = await barrier.queue.get()
    assert ext_name == "slow"
    assert len(blocks) == 0
    assert barrier.is_done()


@pytest.mark.anyio
async def test_streaming_pipeline_integration(event_bus, cache):
    # Mock services
    mock_intent = AsyncMock()
    mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

    mock_strategy = MagicMock()
    sc = MagicMock()
    sc.extractors = ["memory_extractor", "knowledge_extractor"]
    sc.compression_policy = None
    sc.token_budget = MagicMock()
    sc.token_budget.total = 1000
    sc.retrieval_priority = None
    sc.cache_policy = None
    mock_strategy.get_config.return_value = sc
    mock_strategy.intent_type = IntentType.CONVERSATION
    mock_strategy.get_strategy.return_value = mock_strategy

    block_mem = ContextBlock(source="memory/session", content="Mem context", estimated_tokens=10)
    block_know = ContextBlock(source="knowledge/base", content="Know context", estimated_tokens=20)

    mock_extraction = MagicMock()
    mock_mem_ext = AsyncMock()
    mock_mem_ext.extract.return_value = [block_mem]
    mock_know_ext = AsyncMock()
    mock_know_ext.extract.return_value = [block_know]
    mock_extraction.get.side_effect = lambda name: mock_mem_ext if name == "memory_extractor" else mock_know_ext

    # Mock ranking, validator, allocator, compressor, assembler
    mock_ranking = MagicMock()
    mock_ranking.rank.side_effect = lambda blocks, query: RankingResult(
        ranked_blocks=[RankedContextBlock(block=b, relevance_score=0.9, combined_score=0.9) for b in blocks]
    )

    mock_report = MagicMock()
    mock_report.warnings = []
    mock_report.prompt_tokens = 30

    mock_allocator = MagicMock()
    mock_allocator.allocate.side_effect = lambda rbs, config, strategy: type("AllocRes", (), {"selected_blocks": rbs, "report": mock_report})()

    mock_validator = MagicMock()
    mock_validator.validate.side_effect = lambda sbs, strategy: type("ValRes", (), {"valid_blocks": sbs, "report": mock_report})()

    mock_compressor = MagicMock()
    mock_compressor.compress.side_effect = lambda vbs, policy, strategy: CompressionResult(
        compressed_blocks=[CompressedBlock(block=type("AllocBlk", (), {"block": b})()) for b in vbs]
    )

    mock_assembler = MagicMock()
    mock_assembler.assemble.side_effect = lambda compressed_blocks, compression_report=None, budget_report=None, strategy=None, provider="gemini": type("AsmRes", (), {
        "frame": PromptFrame(text_prompt="Assembled context prompt", sections=[]),
        "report": mock_report
    })()

    # Create pipeline and register mock services or context_cache
    pipeline = StreamingPipeline(event_bus=event_bus)

    # Patch modules in pipeline run
    with patch("app.kernel.kernel.FridayKernel") as mock_kernel_cls, \
         patch("app.intelligence.streaming.RuleBasedIntentAnalyzer", return_value=mock_intent), \
         patch("app.intelligence.streaming.StrategyManager", return_value=mock_strategy), \
         patch("app.intelligence.streaming.ContextRanker", return_value=mock_ranking), \
         patch("app.intelligence.streaming.AdaptiveTokenBudgetAllocator", return_value=mock_allocator), \
         patch("app.intelligence.streaming.ContextValidator", return_value=mock_validator), \
         patch("app.intelligence.streaming.ContextCompressor", return_value=mock_compressor), \
         patch("app.intelligence.streaming.PromptAssembler", return_value=mock_assembler):
        
        kernel_instance = MagicMock()
        kernel_instance.get_service.side_effect = lambda name: {
            "extractor_registry": mock_extraction,
            "context_cache": cache,
            "intent_analyzer": mock_intent,
            "strategy_manager": mock_strategy,
            "context_ranker": mock_ranking,
            "token_allocator": mock_allocator,
            "context_validator": mock_validator,
            "context_compressor": mock_compressor,
            "prompt_assembler": mock_assembler,
        }.get(name)
        mock_kernel_cls.get_instance.return_value = kernel_instance

        # Subscribe to streaming events to check emissions
        events_emitted = []
        event_bus.subscribe("StreamingStarted", lambda e: events_emitted.append("started"))
        event_bus.subscribe("ExtractorCompleted", lambda e: events_emitted.append("extractor_completed"))
        event_bus.subscribe("ContextUpdated", lambda e: events_emitted.append("context_updated"))
        event_bus.subscribe("PromptUpdated", lambda e: events_emitted.append("prompt_updated"))
        event_bus.subscribe("StreamingCompleted", lambda e: events_emitted.append("completed"))

        # Execution 1: Cold Cache (both stream in)
        res = await pipeline.execute("test query", session_id="s1")
        assert res.status.value == "completed"
        assert res.prompt_frame.text_prompt == "Assembled context prompt"
        
        # Verify events
        assert "started" in events_emitted
        assert "extractor_completed" in events_emitted
        assert "context_updated" in events_emitted
        assert "prompt_updated" in events_emitted
        assert "completed" in events_emitted
        
        # Execution 2: Cache Hit
        events_emitted.clear()
        res2 = await pipeline.execute("test query", session_id="s1")
        assert res2.status.value == "completed"
        assert res2.metrics.total_hits == 2
        assert res2.metrics.total_misses == 0
