import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.cache.base import (
    CacheKey, CacheLevel, CacheEntry, CacheMetrics, CacheInvalidationPolicy,
    compute_context_hash,
)
from app.cache.cache import ContextCache
from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.extraction.base import ContextBlock, ExtractionResult
from app.ranking.base import RankingResult, RankedContextBlock
from app.compression.base import CompressionResult, CompressedBlock
from app.intelligence.pipeline import IntelligencePipeline, PipelineExecutionContext
from app.intent.analyzer import IntentResult
from app.intent.types import IntentType


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def cache(event_bus):
    return ContextCache(event_bus=event_bus, cleanup_interval=0.1)


@pytest.mark.anyio
async def test_cache_hit(cache, event_bus):
    key = CacheKey(session_id="session_1", extractor="memory_extractor", context_hash="hash_1")
    value = [ContextBlock(source="memory", content="Cached item")]

    hits = []
    event_bus.subscribe("CacheHit", lambda e: hits.append(e))

    await cache.set(key, value, CacheLevel.MEMORY)
    entry = await cache.get(key, CacheLevel.MEMORY)

    assert entry is not None
    assert entry.value[0].content == "Cached item"
    assert cache.metrics().hits == 1
    assert len(hits) == 1
    assert hits[0].data["level"] == "memory"


@pytest.mark.anyio
async def test_cache_miss(cache, event_bus):
    key = CacheKey(session_id="session_1", extractor="memory_extractor", context_hash="hash_1")

    misses = []
    event_bus.subscribe("CacheMiss", lambda e: misses.append(e))

    entry = await cache.get(key, CacheLevel.MEMORY)

    assert entry is None
    assert cache.metrics().misses == 1
    assert len(misses) == 1


@pytest.mark.anyio
async def test_cache_ttl_lazy(cache):
    key = CacheKey(session_id="session_1", extractor="memory_extractor", context_hash="hash_1")
    value = "test_val"

    # Store with TTL of 0.05 seconds
    await cache.set(key, value, CacheLevel.MEMORY, ttl_seconds=0.05)

    # Immediate access works
    entry = await cache.get(key, CacheLevel.MEMORY)
    assert entry is not None

    # Wait for TTL to expire
    await asyncio.sleep(0.08)

    # Get should return None and trigger lazy cleanup
    entry = await cache.get(key, CacheLevel.MEMORY)
    assert entry is None
    assert cache.metrics().expirations >= 1


@pytest.mark.anyio
async def test_cache_ttl_background(cache, event_bus):
    key = CacheKey(session_id="session_1", extractor="memory_extractor", context_hash="hash_1")
    value = "test_val"

    expirations = []
    event_bus.subscribe("CacheExpired", lambda e: expirations.append(e))

    await cache.set(key, value, CacheLevel.MEMORY, ttl_seconds=0.05)
    await cache.start()

    await asyncio.sleep(0.15)
    await cache.shutdown()

    # Background cleanup should have run
    assert cache.metrics().expirations >= 1
    assert len(expirations) >= 1


@pytest.mark.anyio
async def test_cache_lru_eviction(cache):
    # Set limit to 2
    cache._limits[CacheLevel.CONVERSATION] = 2

    k1 = CacheKey(session_id="s1", extractor="c", context_hash="h1")
    k2 = CacheKey(session_id="s1", extractor="c", context_hash="h2")
    k3 = CacheKey(session_id="s1", extractor="c", context_hash="h3")

    await cache.set(k1, "v1", CacheLevel.CONVERSATION)
    await cache.set(k2, "v2", CacheLevel.CONVERSATION)

    # Access k1 so k2 becomes least recently used
    await cache.get(k1, CacheLevel.CONVERSATION)

    # Insert k3, which triggers eviction of k2
    await cache.set(k3, "v3", CacheLevel.CONVERSATION)

    assert await cache.get(k2, CacheLevel.CONVERSATION) is None
    assert await cache.get(k1, CacheLevel.CONVERSATION) is not None
    assert await cache.get(k3, CacheLevel.CONVERSATION) is not None
    assert cache.metrics().evictions == 1


@pytest.mark.anyio
async def test_cache_priority_and_pinning(cache):
    cache._limits[CacheLevel.CONVERSATION] = 2

    k1 = CacheKey(session_id="s1", extractor="c", context_hash="h1")
    k2 = CacheKey(session_id="s1", extractor="c", context_hash="h2")
    k3 = CacheKey(session_id="s1", extractor="c", context_hash="h3")
    k4 = CacheKey(session_id="s1", extractor="c", context_hash="h4")

    # Store k1 as priority, k2 as pinned
    await cache.set(k1, "v1", CacheLevel.CONVERSATION, priority=True)
    await cache.set(k2, "v2", CacheLevel.CONVERSATION, pinned=True)

    # Store k3, should evict k1 because k2 is pinned, even though k1 is priority
    await cache.set(k3, "v3", CacheLevel.CONVERSATION)

    assert await cache.get(k1, CacheLevel.CONVERSATION) is None
    assert await cache.get(k2, CacheLevel.CONVERSATION) is not None
    assert await cache.get(k3, CacheLevel.CONVERSATION) is not None

    # Store k4, should evict k3 because k2 is pinned
    await cache.set(k4, "v4", CacheLevel.CONVERSATION)

    assert await cache.get(k3, CacheLevel.CONVERSATION) is None
    assert await cache.get(k2, CacheLevel.CONVERSATION) is not None
    assert await cache.get(k4, CacheLevel.CONVERSATION) is not None


@pytest.mark.anyio
async def test_cache_partial_invalidation(cache):
    k1 = CacheKey(session_id="session_1", extractor="ext_a", context_hash="h1")
    k2 = CacheKey(session_id="session_1", extractor="ext_b", context_hash="h2")
    k3 = CacheKey(session_id="session_2", extractor="ext_a", context_hash="h3")

    await cache.set(k1, "v1", CacheLevel.MEMORY)
    await cache.set(k2, "v2", CacheLevel.MEMORY)
    await cache.set(k3, "v3", CacheLevel.MEMORY)

    # Invalidate by session_id
    removed = await cache.invalidate(pattern={"session_id": "session_1"}, level=CacheLevel.MEMORY)
    assert removed == 2

    assert await cache.get(k1, CacheLevel.MEMORY) is None
    assert await cache.get(k2, CacheLevel.MEMORY) is None
    assert await cache.get(k3, CacheLevel.MEMORY) is not None

    # Invalidate by extractor
    removed = await cache.invalidate(pattern={"extractor": "ext_a"}, level=CacheLevel.MEMORY)
    assert removed == 1
    assert await cache.get(k3, CacheLevel.MEMORY) is None


@pytest.mark.anyio
async def test_cache_dependency_invalidation(cache):
    k_mem = CacheKey(session_id="s1", extractor="memory_extractor", context_hash="h1")
    k_rank = CacheKey(session_id="s1", extractor="ranker", context_hash="h2")
    k_comp = CacheKey(session_id="s1", extractor="compressor", context_hash="h3")

    await cache.set(k_mem, "mem_val", CacheLevel.MEMORY)
    await cache.set(k_rank, "rank_val", CacheLevel.RANKING_RESULTS)
    await cache.set(k_comp, "comp_val", CacheLevel.COMPRESSED_CONTEXT)

    # Invalidate memory with dependencies
    removed = await cache.invalidate_with_dependencies(CacheLevel.MEMORY)
    # Memory + Ranking Results + Compressed Context = 3 removed
    assert removed == 3

    assert await cache.get(k_mem, CacheLevel.MEMORY) is None
    assert await cache.get(k_rank, CacheLevel.RANKING_RESULTS) is None
    assert await cache.get(k_comp, CacheLevel.COMPRESSED_CONTEXT) is None


@pytest.mark.anyio
async def test_cache_event_auto_invalidation(cache, event_bus):
    k_mem = CacheKey(session_id="session_1", extractor="memory_extractor", context_hash="h1")
    k_rank = CacheKey(session_id="session_1", extractor="ranker", context_hash="h2")

    await cache.set(k_mem, "mem_val", CacheLevel.MEMORY)
    await cache.set(k_rank, "rank_val", CacheLevel.RANKING_RESULTS)

    await cache.start()

    # Publish memory change event
    event = FridayEvent("MemoryUpdated", {"session_id": "session_1"})
    await event_bus.publish(event)

    # Invalidation happens automatically and propagates to dependencies
    assert await cache.get(k_mem, CacheLevel.MEMORY) is None
    assert await cache.get(k_rank, CacheLevel.RANKING_RESULTS) is None

    await cache.shutdown()


@pytest.mark.anyio
async def test_concurrent_access(cache):
    async def task_set(i):
        k = CacheKey(session_id="s1", extractor=f"ext_{i}", context_hash="h")
        await cache.set(k, f"val_{i}", CacheLevel.MEMORY)

    async def task_get(i):
        k = CacheKey(session_id="s1", extractor=f"ext_{i}", context_hash="h")
        return await cache.get(k, CacheLevel.MEMORY)

    # Concurrently write 20 keys
    await asyncio.gather(*(task_set(i) for i in range(20)))

    # Concurrently read 20 keys
    results = await asyncio.gather(*(task_get(i) for i in range(20)))
    for i, res in enumerate(results):
        assert res is not None
        assert res.value == f"val_{i}"


@pytest.mark.anyio
async def test_pipeline_integration(event_bus, cache):
    # Setup mocked components
    mock_intent = AsyncMock()
    mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

    mock_strategy = MagicMock()
    sc = MagicMock()
    sc.extractors = ["memory_extractor", "knowledge_extractor"]
    sc.compression_policy = None
    sc.token_budget = None
    sc.retrieval_priority = None
    sc.cache_policy = None
    mock_strategy.get_config.return_value = sc
    mock_strategy.intent_type = IntentType.CONVERSATION
    mock_strategy.get_strategy.return_value = mock_strategy

    block_mem = ContextBlock(source="memory/session", content="Mem context", estimated_tokens=10)
    block_know = ContextBlock(source="knowledge/base", content="Know context", estimated_tokens=20)

    # Registry mock returns blocks for the extractors run
    mock_extraction = AsyncMock()
    
    # Track extract calls
    extract_calls = []
    
    async def extract_for_strategy_mock(request, config, timeout=10.0):
        extract_calls.append(config.extractors)
        blocks = []
        if "memory_extractor" in config.extractors:
            blocks.append(block_mem)
        if "knowledge_extractor" in config.extractors:
            blocks.append(block_know)
        return ExtractionResult(blocks=blocks)

    mock_extraction.extract_for_strategy = extract_for_strategy_mock

    # Mock ranking, validator, allocator, compressor, assembler
    mock_ranking = MagicMock()
    mock_ranking.rank.return_value = RankingResult(ranked_blocks=[
        RankedContextBlock(block=block_mem, relevance_score=1.0, combined_score=1.0),
        RankedContextBlock(block=block_know, relevance_score=0.9, combined_score=0.9),
    ])

    mock_report = MagicMock()
    mock_report.warnings = []
    mock_report.prompt_tokens = 0

    mock_allocator = MagicMock()
    mock_allocator.allocate.return_value = type("AllocRes", (), {"selected_blocks": [], "report": mock_report})()

    mock_validator = MagicMock()
    mock_validator.validate.return_value = type("ValRes", (), {"valid_blocks": [], "report": mock_report})()

    mock_compressor = MagicMock()
    mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[])

    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = type("AsmRes", (), {"report": mock_report})()

    # Create pipeline and register mock services or context_cache
    pipeline = IntelligencePipeline(event_bus=event_bus)

    # Patch modules in pipeline run
    with patch("app.kernel.kernel.FridayKernel") as mock_kernel_cls, \
         patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=mock_intent), \
         patch("app.intelligence.pipeline.StrategyManager", return_value=mock_strategy), \
         patch("app.intelligence.pipeline.ExtractorRegistry", return_value=mock_extraction), \
         patch("app.intelligence.pipeline.ContextRanker", return_value=mock_ranking), \
         patch("app.intelligence.pipeline.AdaptiveTokenBudgetAllocator", return_value=mock_allocator), \
         patch("app.intelligence.pipeline.ContextValidator", return_value=mock_validator), \
         patch("app.intelligence.pipeline.ContextCompressor", return_value=mock_compressor), \
         patch("app.intelligence.pipeline.PromptAssembler", return_value=mock_assembler):
        
        # FridayKernel singleton mock to return cache
        kernel_instance = MagicMock()
        kernel_instance.get_service.side_effect = lambda name: cache if name == "context_cache" else None
        mock_kernel_cls.get_instance.return_value = kernel_instance

        # Execution 1: Cold Cache
        await cache.start()
        res1 = await pipeline.execute("test query", session_id="s1")
        assert res1.error is None, f"Pipeline execution failed: {res1.error} in stage {res1.failed_stage}"
        assert res1.status.value == "completed"
        print("CACHE METRICS 1:", cache.metrics())
        for lvl, store in cache._stores.items():
            if store:
                print(f"STORE {lvl}: {list(store.keys())}")
        
        # Verify both extractors ran
        assert len(extract_calls) == 1
        assert "memory_extractor" in extract_calls[0]
        assert "knowledge_extractor" in extract_calls[0]

        # Execution 2: Warm Cache
        extract_calls.clear()
        res2 = await pipeline.execute("test query", session_id="s1")
        print("CACHE METRICS 2:", cache.metrics())
        print("EXTRACT CALLS 2:", extract_calls)
        assert res2.status.value == "completed"
        
        # Verify no extractors were called (both hit cache)
        assert len(extract_calls) == 0
        
        # Let's invalidate memory, leaving knowledge cached
        await cache.invalidate(pattern={"extractor": "memory_extractor"}, level=CacheLevel.MEMORY)
        
        # Execution 3: Partial Cache Hit
        extract_calls.clear()
        res3 = await pipeline.execute("test query", session_id="s1")
        assert res3.status.value == "completed"
        
        # Verify only memory_extractor was called, knowledge was cached
        assert len(extract_calls) == 1
        assert "memory_extractor" in extract_calls[0]
        assert "knowledge_extractor" not in extract_calls[0]

        await cache.shutdown()


@pytest.mark.anyio
async def test_cache_stress(cache):
    import random
    
    # Concurrently insert 200 random entries across different levels
    levels = list(CacheLevel)
    tasks = []
    
    for i in range(200):
        level = random.choice(levels)
        key = CacheKey(session_id=f"session_{i % 5}", extractor=f"ext_{i % 10}", context_hash=f"h_{i}")
        priority = random.choice([True, False])
        pinned = random.choice([True, False])
        tasks.append(cache.set(key, f"val_{i}", level, priority=priority, pinned=pinned))
        
    await asyncio.gather(*tasks)

    # Verify cache states are stable
    metrics = cache.metrics()
    assert metrics.stores == 200
    assert cache.get_entry_count() <= sum(cache._limits.values())
    
    # Concurrent reads and invalidates
    read_tasks = []
    for i in range(100):
        level = random.choice(levels)
        key = CacheKey(session_id=f"session_{i % 5}", extractor=f"ext_{i % 10}", context_hash=f"h_{i}")
        read_tasks.append(cache.get(key, level))
        
    await asyncio.gather(*read_tasks)
    
    # Invalidate some sessions
    removed = await cache.invalidate(pattern={"session_id": "session_1"})
    assert removed >= 0
