import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.cache.base import CacheKey, CacheLevel, compute_context_hash
from app.cache.cache import ContextCache
from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.extraction.base import ContextBlock, ExtractionResult
from app.ranking.base import RankingResult, RankedContextBlock
from app.compression.base import CompressionResult, CompressedBlock
from app.assembly.base import PromptFrame, PromptSection
from app.intent.analyzer import IntentResult
from app.intent.types import IntentType
from app.context.base import StrategyConfig

from app.intelligence.incremental import (
    ContextSnapshot,
    ContextDelta,
    DeltaCalculator,
    SnapshotStore,
    IncrementalContextManager,
)


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def cache(event_bus):
    return ContextCache(event_bus=event_bus, cleanup_interval=0.1)


@pytest.fixture
def manager(event_bus):
    return IncrementalContextManager(event_bus=event_bus)


@pytest.mark.anyio
async def test_snapshot_store():
    store = SnapshotStore()
    assert store.get("session_1") is None

    snapshot = ContextSnapshot(
        session_id="session_1",
        query_hash="hash1",
        strategy_signature="sig1",
        timestamp=time.time(),
        valid_blocks=[ContextBlock(source="memory/session", content="content")],
    )
    store.save("session_1", snapshot)

    loaded = store.get("session_1")
    assert loaded is not None
    assert loaded.query_hash == "hash1"
    assert len(loaded.valid_blocks) == 1

    store.invalidate("session_1")
    assert store.get("session_1") is None


def test_delta_calculator():
    strategy_config = StrategyConfig(extractors=["memory_extractor", "knowledge_extractor"])

    # Previous snapshot blocks
    b_mem = ContextBlock(source="memory/session", content="old memory")
    b_know = ContextBlock(source="knowledge/base", content="same knowledge")
    prev_snapshot = ContextSnapshot(
        session_id="s1",
        query_hash="h1",
        strategy_signature="sig",
        timestamp=time.time(),
        valid_blocks=[b_mem, b_know],
    )

    # Freshly extracted blocks
    b_mem_new = ContextBlock(source="memory/session", content="new memory") # updated content
    b_know_new = ContextBlock(source="knowledge/base", content="same knowledge") # reused
    b_workflow = ContextBlock(source="workflow/state", content="new workflow") # new block
    # Note: knowledge_extractor ran but did not return any removed block.
    # What if a block is removed? Suppose "memory/another" was in snapshot but not returned.
    
    b_another = ContextBlock(source="memory/another", content="removed memory")
    prev_snapshot.valid_blocks.append(b_another)

    fresh_blocks = [b_mem_new, b_know_new, b_workflow]

    delta = DeltaCalculator.calculate(prev_snapshot, fresh_blocks, strategy_config)

    assert delta.has_changes
    assert len(delta.new_blocks) == 1
    assert delta.new_blocks[0].source == "workflow/state"

    assert len(delta.updated_blocks) == 1
    assert delta.updated_blocks[0].source == "memory/session"
    assert delta.updated_blocks[0].content == "new memory"

    assert len(delta.reused_blocks) == 1
    assert delta.reused_blocks[0].source == "knowledge/base"

    assert len(delta.removed_blocks) == 1
    assert delta.removed_blocks[0].source == "memory/another"


@pytest.mark.anyio
async def test_event_based_invalidation(manager, event_bus):
    await manager.start()

    # Initial state
    manager._store.save("session_1", ContextSnapshot(
        session_id="session_1", query_hash="h", strategy_signature="s", timestamp=time.time()
    ))

    # Send MemoryUpdated event
    await event_bus.publish(FridayEvent("MemoryUpdated", {"session_id": "session_1"}))
    assert CacheLevel.MEMORY in manager._invalidated_levels["session_1"]

    # Send DocumentIndexed event
    await event_bus.publish(FridayEvent("DocumentIndexed", {}))
    # Global invalidation should affect session_1
    assert CacheLevel.KNOWLEDGE in manager._invalidated_levels["session_1"]

    # Send DesktopChanged event
    await event_bus.publish(FridayEvent("DesktopChanged", {"session_id": "session_1"}))
    assert CacheLevel.DESKTOP in manager._invalidated_levels["session_1"]

    # Clear invalidation
    manager._invalidated_levels["session_1"].clear()

    await manager.shutdown()


@pytest.mark.anyio
async def test_incremental_pipeline_execution(manager, event_bus, cache):
    # Setup mock services in Kernel
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

    mock_extraction = AsyncMock()
    
    # Track extract calls
    extractors_run = []
    async def extract_for_strategy_mock(request, config, timeout=10.0):
        extractors_run.append(config.extractors)
        blocks = []
        if "memory_extractor" in config.extractors:
            blocks.append(block_mem)
        if "knowledge_extractor" in config.extractors:
            blocks.append(block_know)
        return ExtractionResult(blocks=blocks)
    mock_extraction.extract_for_strategy = extract_for_strategy_mock

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
    mock_validator.validate.side_effect = lambda sbs, strategy: type("ValRes", (), {"valid_blocks": [rb.block for rb in sbs], "report": mock_report})()

    mock_compressor = MagicMock()
    mock_compressor.compress.side_effect = lambda vbs, policy, strategy: CompressionResult(
        compressed_blocks=[CompressedBlock(block=type("AllocBlk", (), {"block": b})()) for b in vbs]
    )

    mock_assembler = MagicMock()
    mock_assembler.assemble.side_effect = lambda compressed_blocks, compression_report=None, budget_report=None, strategy=None, provider="gemini": type("AsmRes", (), {
        "frame": PromptFrame(text_prompt="Incremental assembled context prompt", sections=[]),
        "report": mock_report
    })()

    # Kernel mocks
    with patch("app.kernel.kernel.FridayKernel") as mock_kernel_cls, \
         patch("app.intelligence.incremental.RuleBasedIntentAnalyzer", return_value=mock_intent), \
         patch("app.intelligence.incremental.StrategyManager", return_value=mock_strategy), \
         patch("app.intelligence.incremental.ContextRanker", return_value=mock_ranking), \
         patch("app.intelligence.incremental.AdaptiveTokenBudgetAllocator", return_value=mock_allocator), \
         patch("app.intelligence.incremental.ContextValidator", return_value=mock_validator), \
         patch("app.intelligence.incremental.ContextCompressor", return_value=mock_compressor), \
         patch("app.intelligence.incremental.PromptAssembler", return_value=mock_assembler):

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

        # Subscribe to events
        events_emitted = []
        event_bus.subscribe("SnapshotLoaded", lambda e: events_emitted.append("loaded"))
        event_bus.subscribe("ContextDeltaCalculated", lambda e: events_emitted.append("calculated"))
        event_bus.subscribe("SnapshotUpdated", lambda e: events_emitted.append("updated"))
        event_bus.subscribe("IncrementalUpdateCompleted", lambda e: events_emitted.append("completed"))

        await manager.start()

        # Execution 1: Cold start (no snapshot)
        res1 = await manager.execute_incremental("query 1", session_id="session_1")
        assert res1.status.value == "completed"
        assert res1.assembly_result.frame.text_prompt == "Incremental assembled context prompt"
        assert len(extractors_run) == 1
        assert "memory_extractor" in extractors_run[0]
        assert "knowledge_extractor" in extractors_run[0]
        
        # Verify store contains the snapshot
        snap = manager._store.get("session_1")
        assert snap is not None
        assert len(snap.valid_blocks) == 2

        # Execution 2: Warm start - No cache invalidation (100% speedup, 0 extractors re-run!)
        extractors_run.clear()
        events_emitted.clear()
        res2 = await manager.execute_incremental("query 1", session_id="session_1")
        assert res2.status.value == "completed"
        assert len(extractors_run) == 0 # no extractors re-run!
        
        assert "loaded" in events_emitted
        assert "completed" in events_emitted

        # Execution 3: Warm start - Memory invalidated (only memory re-run)
        extractors_run.clear()
        events_emitted.clear()
        await event_bus.publish(FridayEvent("MemoryUpdated", {"session_id": "session_1"}))
        
        res3 = await manager.execute_incremental("query 1", session_id="session_1")
        assert res3.status.value == "completed"
        assert len(extractors_run) == 1
        assert extractors_run[0] == ["memory_extractor"] # only memory ran!

        await manager.shutdown()


@pytest.mark.anyio
async def test_concurrency_stress(manager, event_bus):
    # Stress test simultaneous active sessions and random events
    await manager.start()
    
    async def run_session(i):
        # Cold run
        snap = ContextSnapshot(
            session_id=f"sess_{i}", query_hash="h", strategy_signature="s", timestamp=time.time(),
            valid_blocks=[ContextBlock(source="memory/session", content=f"mem_{i}")]
        )
        manager._store.save(f"sess_{i}", snap)
        
        # Event triggers random invalidation
        await event_bus.publish(FridayEvent("MemoryUpdated", {"session_id": f"sess_{i}"}))
        assert CacheLevel.MEMORY in manager._invalidated_levels[f"sess_{i}"]
        
    await asyncio.gather(*(run_session(i) for i in range(50)))
    
    assert len(manager._store._snapshots) == 50
    assert len(manager._invalidated_levels) == 50
    
    await manager.shutdown()
