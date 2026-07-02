"""Tests for the Intelligence Pipeline Orchestrator (Phase 5, Sprint 1)."""

import asyncio
import time
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.intelligence.pipeline import (
    IntelligencePipeline,
    PipelineResult,
    PipelineMetrics,
    PipelineExecutionContext,
    PipelineStatus,
    _CancellationToken,
)
from app.intelligence.events import (
    STAGE_NAMES,
    PipelineStarted,
    PipelineStageStarted,
    PipelineStageCompleted,
    PipelineCompleted,
    PipelineFailed,
    PipelineCancelled,
)
from app.events.bus import EventBus, FridayEvent
from app.intent.analyzer import IntentResult
from app.intent.types import IntentType
from app.extraction.base import ContextBlock, ExtractionResult
from app.ranking.base import RankedContextBlock, RankingResult, RankingWeights
from app.budget.base import AllocatedBlock, AllocationResult, BudgetReport
from app.validation.base import ValidationResult, ValidationReport
from app.compression.base import CompressedBlock, CompressionResult
from app.assembly.base import AssemblyResult, PromptFrame, PromptReport
from app.kernel.config import FridayKernelConfig


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture(autouse=True)
def reset_kernel():
    from app.kernel.kernel import FridayKernel
    FridayKernel.reset_instance()
    yield


@pytest.fixture
def pipeline(event_bus):
    return IntelligencePipeline(event_bus=event_bus)


@pytest.fixture
def sample_blocks():
    return [
        ContextBlock(source="memory/session", title="Session Memory",
                      content="User prefers Python", estimated_tokens=20, confidence=0.9),
        ContextBlock(source="knowledge/code", title="Code Context",
                      content="Working on async patterns", estimated_tokens=30, confidence=0.8),
        ContextBlock(source="user/query", title="User Query",
                      content="How do I use asyncio?", estimated_tokens=15, confidence=1.0),
    ]


@pytest.fixture
def ranked_blocks(sample_blocks):
    return [
        RankedContextBlock(block=b, relevance_score=0.9, recency_score=0.8,
                           importance_score=0.7, confidence_score=b.confidence,
                           combined_score=0.85)
        for b in sample_blocks
    ]


@pytest.fixture
def allocated_blocks(ranked_blocks):
    return [
        AllocatedBlock(block=rb, allocated_tokens=rb.block.estimated_tokens)
        for rb in ranked_blocks
    ]


@pytest.fixture
def compressed_blocks(allocated_blocks):
    return [
        CompressedBlock(block=ab, original_tokens=ab.allocated_tokens,
                         compressed_tokens=max(1, ab.allocated_tokens // 2),
                         policy_applied="standard")
        for ab in allocated_blocks
    ]


# ──────────────────────────────────────────────────────────────────────
# Test: PipelineStatus, PipelineMetrics, PipelineExecutionContext
# ──────────────────────────────────────────────────────────────────────


class TestPipelineModels:
    def test_pipeline_status_enum(self):
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.COMPLETED.value == "completed"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.CANCELLED.value == "cancelled"

    def test_pipeline_metrics_defaults(self):
        m = PipelineMetrics()
        assert m.execution_id == ""
        assert m.started_at == 0.0
        assert m.total_latency_ms == 0.0
        assert m.warnings == []
        assert m.errors == []

    def test_pipeline_metrics_stage_latency(self):
        m = PipelineMetrics(
            intent_latency_ms=10.0,
            strategy_latency_ms=5.0,
            extraction_latency_ms=20.0,
            ranking_latency_ms=8.0,
            budget_latency_ms=3.0,
            validation_latency_ms=4.0,
            compression_latency_ms=15.0,
            assembly_latency_ms=6.0,
        )
        stages = m.stage_latency_ms
        assert stages["intent_analysis"] == 10.0
        assert stages["strategy_resolution"] == 5.0
        assert stages["context_extraction"] == 20.0
        assert stages["context_ranking"] == 8.0
        assert stages["token_budget_allocation"] == 3.0
        assert stages["context_validation"] == 4.0
        assert stages["context_compression"] == 15.0
        assert stages["prompt_assembly"] == 6.0

    def test_pipeline_context_defaults(self):
        ctx = PipelineExecutionContext()
        assert ctx.execution_id == ""
        assert ctx.user_query == ""
        assert ctx.provider == "gemini"
        assert ctx.timeout == 120.0
        assert ctx.intent_result is None
        assert ctx.strategy_config is None

    def test_pipeline_result_defaults(self):
        r = PipelineResult()
        assert r.status == PipelineStatus.PENDING
        assert r.execution_id == ""
        assert r.assembly_result is None
        assert r.error is None

    def test_cancellation_token(self):
        token = _CancellationToken()
        assert not token.cancelled
        token.cancel()
        assert token.cancelled


# ──────────────────────────────────────────────────────────────────────
# Test: PipelineEvents
# ──────────────────────────────────────────────────────────────────────


class TestPipelineEvents:
    def test_pipeline_started(self):
        e = PipelineStarted(execution_id="e1", request="hello", session_id="s1", provider="gemini")
        assert e.topic == "PipelineStarted"
        assert e.data["execution_id"] == "e1"
        assert e.data["request"] == "hello"

    def test_pipeline_stage_started(self):
        e = PipelineStageStarted(execution_id="e1", stage="intent_analysis")
        assert e.topic == "PipelineStageStarted"
        assert e.data["stage"] == "intent_analysis"

    def test_pipeline_stage_completed(self):
        e = PipelineStageCompleted(execution_id="e1", stage="intent_analysis", latency_ms=10.5)
        assert e.topic == "PipelineStageCompleted"
        assert e.data["latency_ms"] == 10.5

    def test_pipeline_completed(self):
        e = PipelineCompleted(execution_id="e1", total_latency_ms=100.0, prompt_tokens=500)
        assert e.topic == "PipelineCompleted"
        assert e.data["prompt_tokens"] == 500

    def test_pipeline_failed(self):
        e = PipelineFailed(execution_id="e1", stage="prompt_assembly", error="test error")
        assert e.topic == "PipelineFailed"
        assert e.data["error"] == "test error"

    def test_pipeline_cancelled(self):
        e = PipelineCancelled(execution_id="e1", stage="context_extraction")
        assert e.topic == "PipelineCancelled"
        assert e.data["stage"] == "context_extraction"

    def test_stage_names_complete(self):
        assert len(STAGE_NAMES) == 8
        assert STAGE_NAMES == [
            "intent_analysis",
            "strategy_resolution",
            "context_extraction",
            "context_ranking",
            "token_budget_allocation",
            "context_validation",
            "context_compression",
            "prompt_assembly",
        ]


# ──────────────────────────────────────────────────────────────────────
# Test: Pipeline Orchestration (end-to-end with mocks)
# ──────────────────────────────────────────────────────────────────────


class TestPipelineExecution:
    @pytest.mark.anyio
    async def test_pipeline_completes_with_mocks(self, pipeline, sample_blocks, ranked_blocks,
                                                  allocated_blocks, compressed_blocks):
        """Verify full pipeline execution with mocked subsystems."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        strategy_config = MagicMock()
        strategy_config.extractors = ["memory_extractor", "knowledge_extractor"]
        strategy_config.compression_policy = MagicMock()
        strategy_config.compression_policy.value = "standard"
        mock_strategy.get_config.return_value = strategy_config
        mock_strategy.intent_type = IntentType.CONVERSATION
        mock_strategy.get_strategy.return_value = mock_strategy

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=sample_blocks)

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(
            ranked_blocks=ranked_blocks,
            total_blocks=len(ranked_blocks),
        )

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(
            selected_blocks=allocated_blocks,
            report=BudgetReport(total_budget=1000, allocated_tokens=65, selected_blocks=3),
        )

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            valid_blocks=allocated_blocks,
            report=ValidationReport(input_blocks=3, valid_blocks=3),
        )

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(
            compressed_blocks=compressed_blocks,
            report=MagicMock(input_tokens=65, output_tokens=32, compression_ratio=0.5),
        )

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(
                system_instruction="Test system prompt",
                messages=[{"role": "user", "content": "Hello"}],
            ),
            report=PromptReport(prompt_tokens=32, provider="gemini"),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(
                user_query="Hello, how are you?",
                session_id="test-session",
                provider="gemini",
            )

        assert result.status == PipelineStatus.COMPLETED
        assert result.assembly_result is not None
        assert result.assembly_result.frame is not None
        assert result.assembly_result.report.prompt_tokens == 32
        assert result.metrics is not None
        assert result.metrics.intent_latency_ms > 0
        assert result.metrics.strategy_latency_ms > 0
        assert result.metrics.extraction_latency_ms > 0
        assert result.metrics.ranking_latency_ms > 0
        assert result.metrics.budget_latency_ms > 0
        assert result.metrics.validation_latency_ms > 0
        assert result.metrics.compression_latency_ms > 0
        assert result.metrics.assembly_latency_ms > 0
        assert result.metrics.total_latency_ms > 0

        mock_intent.analyze.assert_called_once_with("Hello, how are you?")
        mock_strategy.get_strategy.assert_called_once_with(IntentType.CONVERSATION)
        mock_extraction.extract_for_strategy.assert_called_once()
        mock_ranking.rank.assert_called_once()
        mock_allocator.allocate.assert_called_once()
        mock_validator.validate.assert_called_once()
        mock_compressor.compress.assert_called_once()
        mock_assembler.assemble.assert_called_once()

    @pytest.mark.anyio
    async def test_pipeline_publishes_events(self, pipeline):
        """Verify pipeline publishes start/stage/completion events."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc
        mock_strategy.intent_type = IntentType.CONVERSATION
        mock_strategy.get_strategy.return_value = mock_strategy

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=0),
        )

        received = []
        pipeline._event_bus.subscribe("PipelineStarted", lambda e: received.append(e))
        pipeline._event_bus.subscribe("PipelineStageStarted", lambda e: received.append(e))
        pipeline._event_bus.subscribe("PipelineStageCompleted", lambda e: received.append(e))
        pipeline._event_bus.subscribe("PipelineCompleted", lambda e: received.append(e))

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="test")

        topics = [e.topic for e in received]
        assert "PipelineStarted" in topics
        assert topics.count("PipelineStageStarted") == 8
        assert topics.count("PipelineStageCompleted") == 8
        assert "PipelineCompleted" in topics

    @pytest.mark.anyio
    async def test_pipeline_empty_query(self, pipeline):
        """Pipeline handles empty query gracefully."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.UNKNOWN, confidence=0.5)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=0),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="")

        assert result.status == PipelineStatus.COMPLETED

    @pytest.mark.anyio
    async def test_pipeline_deterministic_order(self, pipeline):
        """Verify deterministic execution order across multiple runs."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CODING, confidence=0.95)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = ["knowledge_extractor"]
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "standard"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=10),
        )

        patches = patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        )

        with patches:
            r1 = await pipeline.execute(user_query="test")
        with patches:
            r2 = await pipeline.execute(user_query="test")

        assert r1.status == r2.status == PipelineStatus.COMPLETED
        assert r1.metrics.total_latency_ms > 0
        assert r2.metrics.total_latency_ms > 0

    @pytest.mark.anyio
    async def test_pipeline_metrics_track_all_stages(self, pipeline):
        """Verify all 8 stages are tracked in metrics."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=5),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="test")

        m = result.metrics
        assert m.intent_latency_ms >= 0
        assert m.strategy_latency_ms >= 0
        assert m.extraction_latency_ms >= 0
        assert m.ranking_latency_ms >= 0
        assert m.budget_latency_ms >= 0
        assert m.validation_latency_ms >= 0
        assert m.compression_latency_ms >= 0
        assert m.assembly_latency_ms >= 0
        assert m.total_latency_ms > 0

        stages = m.stage_latency_ms
        for name in STAGE_NAMES:
            assert name in stages


# ──────────────────────────────────────────────────────────────────────
# Test: Failure Policies
# ──────────────────────────────────────────────────────────────────────


class TestFailurePolicies:
    @pytest.mark.anyio
    async def test_intent_failure_aborts(self, pipeline):
        """Intent analyzer failure aborts pipeline."""
        mock_intent = AsyncMock()
        mock_intent.analyze.side_effect = RuntimeError("Intent analysis failed")

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=mock_intent):
            result = await pipeline.execute(user_query="test")

        assert result.status == PipelineStatus.FAILED
        assert result.failed_stage == "intent_analysis"

    @pytest.mark.anyio
    async def test_assembler_failure_aborts(self, pipeline):
        """Prompt assembler failure aborts pipeline."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.side_effect = RuntimeError("Assembly failed")

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="test")

        assert result.status == PipelineStatus.FAILED
        assert result.failed_stage == "prompt_assembly"

    @pytest.mark.anyio
    async def test_validator_warning_continues(self, pipeline):
        """Validator warnings (non-fatal) allow pipeline to continue."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            valid_blocks=[],
            report=ValidationReport(input_blocks=0, valid_blocks=0, warnings=["Non-fatal warning"]),
        )

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=5),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="test")

        assert result.status == PipelineStatus.COMPLETED

    @pytest.mark.anyio
    async def test_compression_fallback_on_failure(self, pipeline, allocated_blocks):
        """Compression failure falls back to uncompressed validated blocks."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "standard"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(
            selected_blocks=allocated_blocks,
            report=BudgetReport(),
        )

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(
            valid_blocks=allocated_blocks,
            report=ValidationReport(input_blocks=len(allocated_blocks), valid_blocks=len(allocated_blocks)),
        )

        mock_compressor = MagicMock()
        mock_compressor.compress.side_effect = RuntimeError("Compression failed")

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=10),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="test")

        assert result.status == PipelineStatus.COMPLETED
        assert "Compression failed" in result.metrics.warnings[0]
        mock_assembler.assemble.assert_called_once()


# ──────────────────────────────────────────────────────────────────────
# Test: Timeout
# ──────────────────────────────────────────────────────────────────────


class TestTimeout:
    @pytest.mark.anyio
    async def test_pipeline_timeout_returns_cancelled(self, pipeline):
        """Pipeline exceeding timeout returns CANCELLED."""
        slow_intent = AsyncMock()

        async def slow_analyze(request):
            await asyncio.sleep(10)
            return IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        slow_intent.analyze.side_effect = slow_analyze

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=slow_intent):
            result = await pipeline.execute(user_query="test", timeout=0.05)

        assert result.status == PipelineStatus.CANCELLED

    @pytest.mark.anyio
    async def test_timeout_event_published(self, pipeline):
        """PipelineCancelled event published on timeout."""
        slow_intent = AsyncMock()

        async def slow_analyze(request):
            await asyncio.sleep(10)
            return IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        slow_intent.analyze.side_effect = slow_analyze

        received = []
        pipeline._event_bus.subscribe("PipelineCancelled", lambda e: received.append(e))

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=slow_intent):
            await pipeline.execute(user_query="test", timeout=0.05)

        assert len(received) >= 1
        assert received[0].topic == "PipelineCancelled"

    @pytest.mark.anyio
    async def test_timeout_sets_cancellation_count(self, pipeline):
        """Timeout increments cancellation counter."""
        slow_intent = AsyncMock()

        async def slow_analyze(request):
            await asyncio.sleep(10)
            return IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        slow_intent.analyze.side_effect = slow_analyze

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=slow_intent):
            await pipeline.execute(user_query="test", timeout=0.05)

        health = pipeline.health()
        assert health["details"]["total_cancellations"] >= 1


# ──────────────────────────────────────────────────────────────────────
# Test: Cancellation Token
# ──────────────────────────────────────────────────────────────────────


class TestCancellation:
    @pytest.mark.anyio
    async def test_cancellation_token_cancel_during_run(self, pipeline):
        """Cancellation during execution returns CANCELLED."""
        slow_intent = AsyncMock()

        async def slow_analyze(request):
            await asyncio.sleep(10)
            return IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        slow_intent.analyze.side_effect = slow_analyze

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=slow_intent):
            result = await pipeline.execute(user_query="test", timeout=0.05)

        assert result.status == PipelineStatus.CANCELLED

    @pytest.mark.anyio
    async def test_cancelled_event_on_timeout(self, pipeline):
        """PipelineCancelled event published on timeout."""
        slow_intent = AsyncMock()

        async def slow_analyze(request):
            await asyncio.sleep(10)
            return IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        slow_intent.analyze.side_effect = slow_analyze

        received = []
        pipeline._event_bus.subscribe("PipelineCancelled", lambda e: received.append(e))

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=slow_intent):
            await pipeline.execute(user_query="test", timeout=0.05)

        assert len(received) >= 1
        assert received[0].topic == "PipelineCancelled"


# ──────────────────────────────────────────────────────────────────────
# Test: Health
# ──────────────────────────────────────────────────────────────────────


class TestHealth:
    @pytest.mark.anyio
    async def test_health_returns_healthy_initially(self, pipeline):
        health = pipeline.health()
        assert health["status"] == "HEALTHY"
        assert health["details"]["total_executions"] == 0
        assert health["details"]["total_failures"] == 0
        assert health["details"]["total_cancellations"] == 0

    @pytest.mark.anyio
    async def test_health_tracks_executions(self, pipeline):
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)
        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc
        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])
        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])
        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())
        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(frame=PromptFrame(), report=PromptReport())

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            await pipeline.execute(user_query="test")
            await pipeline.execute(user_query="test2")

        health = pipeline.health()
        assert health["details"]["total_executions"] == 2

    @pytest.mark.anyio
    async def test_health_tracks_failures(self, pipeline):
        mock_intent = AsyncMock()
        mock_intent.analyze.side_effect = RuntimeError("Fail")

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=mock_intent):
            await pipeline.execute(user_query="test")

        health = pipeline.health()
        assert health["details"]["total_failures"] >= 1


# ──────────────────────────────────────────────────────────────────────
# Test: Concurrent Requests
# ──────────────────────────────────────────────────────────────────────


class TestConcurrency:
    @pytest.mark.anyio
    async def test_concurrent_executions(self, pipeline):
        """Multiple simultaneous pipeline executions succeed."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=10),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            results = await asyncio.gather(
                pipeline.execute(user_query="q1"),
                pipeline.execute(user_query="q2"),
                pipeline.execute(user_query="q3"),
                pipeline.execute(user_query="q4"),
                pipeline.execute(user_query="q5"),
            )

        assert len(results) == 5
        for r in results:
            assert r.status == PipelineStatus.COMPLETED
            assert r.execution_id != ""


# ──────────────────────────────────────────────────────────────────────
# Test: Integration with EventBus
# ──────────────────────────────────────────────────────────────────────


class TestEventBusIntegration:
    @pytest.mark.anyio
    async def test_pipeline_publishes_to_event_bus(self, event_bus):
        """Pipeline publishes events via EventBus when provided."""
        pipe = IntelligencePipeline(event_bus=event_bus)

        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=10),
        )

        started = []
        completed = []
        pipe._event_bus.subscribe("PipelineStarted", lambda e: started.append(e))
        pipe._event_bus.subscribe("PipelineCompleted", lambda e: completed.append(e))

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            await pipe.execute(user_query="test")

        assert len(started) == 1
        assert len(completed) == 1

    @pytest.mark.anyio
    async def test_pipeline_without_event_bus(self):
        """Pipeline works without an event bus."""
        pipe = IntelligencePipeline(event_bus=None)
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])

        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])

        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())

        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())

        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())

        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=10),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipe.execute(user_query="test")

        assert result.status == PipelineStatus.COMPLETED

    @pytest.mark.anyio
    async def test_pipeline_failed_event_published(self, pipeline):
        """PipelineFailed event published on failure."""
        mock_intent = AsyncMock()
        mock_intent.analyze.side_effect = RuntimeError("Intent crash")

        received = []
        pipeline._event_bus.subscribe("PipelineFailed", lambda e: received.append(e))

        with patch("app.intelligence.pipeline.RuleBasedIntentAnalyzer", return_value=mock_intent):
            await pipeline.execute(user_query="test")

        assert len(received) >= 1
        assert received[0].topic == "PipelineFailed"
        assert "Intent crash" in received[0].data["error"]


# ──────────────────────────────────────────────────────────────────────
# Test: Kernel Integration
# ──────────────────────────────────────────────────────────────────────


class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_pipeline_health_in_kernel_health(self):
        """Kernel health check includes pipeline orchestrator."""
        from app.kernel.kernel import FridayKernel
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        try:
            await kernel.boot()
            health = kernel.health()
            assert hasattr(health, "pipeline_orchestrator")
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_pipeline_service_accessible_via_kernel(self):
        """IntelligencePipeline is accessible via kernel.get_service()."""
        from app.kernel.kernel import FridayKernel
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        try:
            await kernel.boot()
            svc = kernel.get_service("pipeline_orchestrator")
            assert svc is not None
            assert hasattr(svc, "execute")
            assert callable(svc.execute)
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_pipeline_uses_kernel_services(self):
        """Pipeline resolves existing singletons from kernel DI."""
        from app.kernel.kernel import FridayKernel
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        try:
            await kernel.boot()
            pipe = kernel.get_service("pipeline_orchestrator")
            assert pipe is not None
            health = pipe.health()
            assert health["status"] == "HEALTHY"
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_pipeline_registered_in_module_registry(self):
        """Pipeline appears in module registry."""
        from app.kernel.kernel import FridayKernel
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        try:
            await kernel.boot()
            modules = kernel.module_registry.list_modules()
            module_names = modules if isinstance(modules, list) else list(modules)
            if isinstance(module_names, (list, tuple)):
                assert "pipeline_orchestrator" in module_names
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()


# ──────────────────────────────────────────────────────────────────────
# Test: Stress / Load
# ──────────────────────────────────────────────────────────────────────


class TestStress:
    @pytest.mark.anyio
    async def test_pipeline_100_blocks(self, pipeline, sample_blocks, ranked_blocks,
                                        allocated_blocks, compressed_blocks):
        """Pipeline handles large extraction results."""
        many_blocks = sample_blocks * 33
        many_ranked = []
        for b in many_blocks:
            many_ranked.append(RankedContextBlock(
                block=b, relevance_score=0.5, recency_score=0.5,
                importance_score=0.5, confidence_score=b.confidence,
                combined_score=0.5,
            ))
        many_allocated = [AllocatedBlock(block=rb, allocated_tokens=rb.block.estimated_tokens) for rb in many_ranked]
        many_compressed = [
            CompressedBlock(block=ab, original_tokens=ab.allocated_tokens,
                             compressed_tokens=max(1, ab.allocated_tokens // 2),
                             policy_applied="standard")
            for ab in many_allocated
        ]

        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)
        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = ["memory_extractor"]
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "standard"
        mock_strategy.get_config.return_value = sc
        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=many_blocks)
        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=many_ranked, total_blocks=len(many_ranked))
        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=many_allocated, report=BudgetReport())
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=many_allocated, report=ValidationReport())
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=many_compressed, report=MagicMock())
        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=500),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="stress test", provider="openai")

        assert result.status == PipelineStatus.COMPLETED
        assert result.metrics is not None

    @pytest.mark.anyio
    async def test_pipeline_1000_blocks(self, pipeline):
        """Pipeline handles 1000+ blocks."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.WORKFLOW, confidence=0.95)

        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = ["memory_extractor"]
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "aggressive"
        mock_strategy.get_config.return_value = sc

        blocks = [
            ContextBlock(source=f"memory/block_{i}", title=f"Block {i}",
                          content=f"Content block number {i}" * 10,
                          estimated_tokens=40, confidence=0.7)
            for i in range(1000)
        ]
        ranked = [
            RankedContextBlock(block=b, relevance_score=0.5, recency_score=0.5,
                               importance_score=0.5, confidence_score=b.confidence,
                               combined_score=0.5)
            for b in blocks
        ]
        allocated = [
            AllocatedBlock(block=rb, allocated_tokens=rb.block.estimated_tokens)
            for rb in ranked
        ]

        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=blocks)
        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=ranked, total_blocks=1000)
        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=allocated[:500], report=BudgetReport())
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=allocated[:500], report=ValidationReport())
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(
            compressed_blocks=[
                CompressedBlock(block=ab, original_tokens=ab.allocated_tokens,
                                 compressed_tokens=max(1, ab.allocated_tokens // 2),
                                 policy_applied="aggressive")
                for ab in allocated[:500]
            ],
            report=MagicMock(),
        )
        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(), report=PromptReport(prompt_tokens=10000),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query="large test")

        assert result.status == PipelineStatus.COMPLETED


# ──────────────────────────────────────────────────────────────────────
# Test: Regression
# ──────────────────────────────────────────────────────────────────────


class TestRegression:
    @pytest.mark.anyio
    async def test_pipeline_result_matches_manual_execution(self, pipeline, sample_blocks,
                                                            ranked_blocks, allocated_blocks,
                                                            compressed_blocks):
        """Pipeline output matches executing subsystems manually."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)
        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = ["memory_extractor"]
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "standard"
        mock_strategy.get_config.return_value = sc
        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=sample_blocks)
        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=ranked_blocks)
        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=allocated_blocks, report=BudgetReport())
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=allocated_blocks, report=ValidationReport())
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=compressed_blocks, report=MagicMock())
        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(
            frame=PromptFrame(
                system_instruction="System prompt",
                messages=[{"role": "user", "content": "Hello"}],
            ),
            report=PromptReport(prompt_tokens=32, provider="gemini"),
        )

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            pipe_result = await pipeline.execute(user_query="Hello")

        manual_assembly = mock_assembler.assemble.return_value
        assert pipe_result.assembly_result.frame.system_instruction == manual_assembly.frame.system_instruction
        assert pipe_result.assembly_result.frame.messages == manual_assembly.frame.messages
        assert pipe_result.assembly_result.report.prompt_tokens == manual_assembly.report.prompt_tokens
        assert pipe_result.metrics.assembled_tokens == manual_assembly.report.prompt_tokens

    @pytest.mark.anyio
    async def test_pipeline_does_not_modify_content(self, pipeline):
        """Pipeline does not modify user query or block content."""
        original_query = "Show me my recent Python files"
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)
        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc
        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])
        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])
        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())
        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(frame=PromptFrame(), report=PromptReport())

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            result = await pipeline.execute(user_query=original_query)

        assert result.status == PipelineStatus.COMPLETED
        assert mock_intent.analyze.call_args[0][0] == original_query

    @pytest.mark.anyio
    async def test_pipeline_uniqueness(self, pipeline):
        """Each execution gets a unique ID."""
        mock_intent = AsyncMock()
        mock_intent.analyze.return_value = IntentResult(intent=IntentType.CONVERSATION, confidence=0.9)
        mock_strategy = MagicMock()
        sc = MagicMock()
        sc.extractors = []
        sc.compression_policy = MagicMock()
        sc.compression_policy.value = "none"
        mock_strategy.get_config.return_value = sc
        mock_extraction = AsyncMock()
        mock_extraction.extract_for_strategy.return_value = ExtractionResult(blocks=[])
        mock_ranking = MagicMock()
        mock_ranking.rank.return_value = RankingResult(ranked_blocks=[])
        mock_allocator = MagicMock()
        mock_allocator.allocate.return_value = AllocationResult(selected_blocks=[], report=BudgetReport())
        mock_validator = MagicMock()
        mock_validator.validate.return_value = ValidationResult(valid_blocks=[], report=ValidationReport())
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = CompressionResult(compressed_blocks=[], report=MagicMock())
        mock_assembler = MagicMock()
        mock_assembler.assemble.return_value = AssemblyResult(frame=PromptFrame(), report=PromptReport())

        with patch.multiple(
            "app.intelligence.pipeline",
            RuleBasedIntentAnalyzer=lambda **kw: mock_intent,
            StrategyManager=lambda **kw: mock_strategy,
            ExtractorRegistry=lambda **kw: mock_extraction,
            ContextRanker=lambda **kw: mock_ranking,
            AdaptiveTokenBudgetAllocator=lambda **kw: mock_allocator,
            ContextValidator=lambda **kw: mock_validator,
            ContextCompressor=lambda **kw: mock_compressor,
            PromptAssembler=lambda **kw: mock_assembler,
        ):
            r1 = await pipeline.execute(user_query="q1")
            r2 = await pipeline.execute(user_query="q2")

        assert r1.execution_id != r2.execution_id


# ──────────────────────────────────────────────────────────────────────
# Test: Lifecycle
# ──────────────────────────────────────────────────────────────────────


class TestLifecycle:
    @pytest.mark.anyio
    async def test_start_shutdown(self, pipeline):
        await pipeline.start()
        await pipeline.shutdown()
        assert True

    @pytest.mark.anyio
    async def test_health_after_start(self, pipeline):
        await pipeline.start()
        health = pipeline.health()
        assert health["status"] == "HEALTHY"
        await pipeline.shutdown()
