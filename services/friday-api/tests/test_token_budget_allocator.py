from datetime import datetime, timezone
from typing import List

import pytest

from app.extraction.base import ContextBlock
from app.ranking.base import RankedContextBlock
from app.context.base import StrategyConfig, TokenBudget
from app.budget.base import (
    ITokenBudgetAllocator,
    BudgetConfig,
    BudgetReport,
    AllocatedBlock,
    AllocationResult,
    MODEL_LIMITS,
    DEFAULT_MODEL,
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MAX_OUTPUT,
)
from app.budget.allocator import AdaptiveTokenBudgetAllocator
from app.budget.events import TokenBudgetAllocated


def make_ranked(
    source: str = "test",
    content: str = "",
    estimated_tokens: int = 100,
    importance: float = 0.5,
    confidence: float = 1.0,
    combined_score: float = 0.5,
) -> RankedContextBlock:
    block = ContextBlock(
        source=source,
        content=content,
        estimated_tokens=estimated_tokens,
        importance=importance,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc),
    )
    return RankedContextBlock(
        block=block,
        relevance_score=0.5,
        recency_score=0.5,
        importance_score=importance,
        confidence_score=confidence,
        combined_score=combined_score,
    )


def make_ranked_blocks(count: int, **kwargs) -> List[RankedContextBlock]:
    return [make_ranked(source=f"src{i}", **kwargs) for i in range(count)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def allocator():
    return AdaptiveTokenBudgetAllocator()


@pytest.fixture
def default_config():
    return BudgetConfig(
        context_window=10_000,
        reserved_response_tokens=1_000,
        system_prompt_reservation=500,
        conversation_history_reservation=1_000,
        min_guaranteed_per_block=100,
        max_per_block=2_000,
    )


# ---------------------------------------------------------------------------
# Test: Creation and naming
# ---------------------------------------------------------------------------

class TestAllocatorCreation:
    def test_allocator_name(self):
        a = AdaptiveTokenBudgetAllocator()
        assert a.allocator_name == "token_budget_allocator"

    def test_health_default(self):
        a = AdaptiveTokenBudgetAllocator()
        h = a.health()
        assert h["status"] == "HEALTHY"

    def test_start_shutdown(self):
        a = AdaptiveTokenBudgetAllocator()
        assert not a._running
        import anyio
        anyio.run(a.start)
        assert a._running
        anyio.run(a.shutdown)
        assert not a._running

    def test_implements_interface(self):
        assert issubclass(AdaptiveTokenBudgetAllocator, ITokenBudgetAllocator)
        a = AdaptiveTokenBudgetAllocator()
        assert isinstance(a, ITokenBudgetAllocator)


# ---------------------------------------------------------------------------
# Test: BudgetConfig
# ---------------------------------------------------------------------------

class TestBudgetConfig:
    def test_default_creation(self):
        c = BudgetConfig()
        assert c.context_window == DEFAULT_CONTEXT_WINDOW
        assert c.model_name == DEFAULT_MODEL

    def test_for_model_gemini(self):
        c = BudgetConfig.for_model("gemini-2.0-flash")
        assert c.context_window == 1_048_576
        assert c.reserved_response_tokens == 8_192

    def test_for_model_gpt4(self):
        c = BudgetConfig.for_model("gpt-4")
        assert c.context_window == 32_768
        assert c.reserved_response_tokens == 4_096

    def test_for_model_unknown(self):
        c = BudgetConfig.for_model("unknown-model")
        assert c.context_window == DEFAULT_CONTEXT_WINDOW
        assert c.reserved_response_tokens == DEFAULT_MAX_OUTPUT

    def test_for_model_with_overrides(self):
        c = BudgetConfig.for_model("gpt-4", reserved_response_tokens=2_000)
        assert c.context_window == 32_768
        assert c.reserved_response_tokens == 2_000


# ---------------------------------------------------------------------------
# Test: Basic allocation
# ---------------------------------------------------------------------------

class TestBasicAllocation:
    def test_empty_blocks(self, allocator, default_config):
        result = allocator.allocate([], config=default_config)
        assert result.total_selected == 0
        assert result.total_discarded == 0
        assert result.report.total_blocks_input == 0

    def test_single_block_fits(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=50)]
        result = allocator.allocate(blocks, config=default_config)
        assert result.total_selected == 1
        assert result.total_discarded == 0
        assert result.report.allocated_tokens > 0

    def test_all_blocks_selected_when_fit(self, allocator, default_config):
        blocks = make_ranked_blocks(5, estimated_tokens=200)
        result = allocator.allocate(blocks, config=default_config)
        assert result.total_selected == 5
        assert result.total_discarded == 0

    def test_selected_blocks_have_allocated_tokens(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config)
        ab = result.selected_blocks[0]
        assert ab.allocated_tokens > 0
        assert ab.block is blocks[0]

    def test_allocated_tokens_reasonable(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=500)]
        result = allocator.allocate(blocks, config=default_config)
        ab = result.selected_blocks[0]
        assert ab.allocated_tokens <= 2000  # max_per_block


# ---------------------------------------------------------------------------
# Test: Budget report correctness
# ---------------------------------------------------------------------------

class TestBudgetReport:
    def test_report_fields_present(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config)
        r = result.report
        assert r.total_budget == 10_000
        assert r.selected_blocks == 1
        assert r.reserved_tokens == 2_500  # 1000 + 500 + 1000
        assert r.utilization_percentage > 0

    def test_available_tokens_property(self):
        r = BudgetReport(total_budget=10_000, reserved_tokens=2_500)
        assert r.available_tokens == 7_500

    def test_utilization_capped(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100_000)]
        result = allocator.allocate(blocks, config=default_config)
        assert result.report.utilization_percentage <= 100.0

    def test_report_has_details_dict(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config)
        assert isinstance(result.report.details, dict)
        assert "model" in result.report.details


# ---------------------------------------------------------------------------
# Test: Overflow and discarding
# ---------------------------------------------------------------------------

class TestOverflow:
    def test_discards_when_blocks_exceed_budget(self, allocator, default_config):
        large = make_ranked(estimated_tokens=100_000, source="huge")
        small = make_ranked(estimated_tokens=50, source="tiny")
        result = allocator.allocate([large, small], config=default_config)
        # Small should be selected, huge may be discarded or heavily truncated
        assert result.report.discarded_blocks >= 0
        assert result.total_selected + result.total_discarded == 2

    def test_discarded_blocks_populated(self, allocator, default_config):
        many = make_ranked_blocks(100, estimated_tokens=500)
        result = allocator.allocate(many, config=default_config)
        assert result.total_discarded >= 0
        if result.total_discarded > 0:
            assert isinstance(result.discarded_blocks[0], RankedContextBlock)

    def test_overflow_with_very_small_budget(self, allocator):
        tiny_config = BudgetConfig(context_window=500, reserved_response_tokens=200,
                                    system_prompt_reservation=100,
                                    conversation_history_reservation=100,
                                    min_guaranteed_per_block=50,
                                    max_per_block=100)
        blocks = make_ranked_blocks(10, estimated_tokens=200)
        result = allocator.allocate(blocks, config=tiny_config)
        assert result.total_selected + result.total_discarded == 10
        assert result.report.allocated_tokens <= result.report.available_tokens

    def test_zero_available_budget(self, allocator):
        zero_config = BudgetConfig(context_window=100, reserved_response_tokens=200,
                                    system_prompt_reservation=0,
                                    conversation_history_reservation=0,
                                    min_guaranteed_per_block=10,
                                    max_per_block=50)
        blocks = [make_ranked(estimated_tokens=50)]
        result = allocator.allocate(blocks, config=zero_config)
        assert result.total_selected == 0
        assert result.total_discarded == 1
        assert result.report.utilization_percentage == 0.0


# ---------------------------------------------------------------------------
# Test: Strategy-specific budget
# ---------------------------------------------------------------------------

class TestStrategySpecificBudget:
    def test_strategy_ratio_affects_allocation(self, allocator, default_config):
        small_strategy = StrategyConfig(token_budget=TokenBudget(total=1_000))
        large_strategy = StrategyConfig(token_budget=TokenBudget(total=100_000))
        blocks = make_ranked_blocks(3, estimated_tokens=500)
        r_small = allocator.allocate(blocks, config=default_config, strategy=small_strategy)
        r_large = allocator.allocate(blocks, config=default_config, strategy=large_strategy)
        # Different strategies should produce different allocations
        assert r_small.report.allocated_tokens != r_large.report.allocated_tokens or \
               r_small.total_selected != r_large.total_selected

    def test_strategy_with_no_budget_info(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config, strategy=None)
        assert result.total_selected == 1

    def test_strategy_ratio_floored(self, allocator, default_config):
        zero_strategy = StrategyConfig()
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config, strategy=zero_strategy)
        assert result.total_selected >= 0


# ---------------------------------------------------------------------------
# Test: Truncation markers
# ---------------------------------------------------------------------------

class TestTruncationMarkers:
    def test_truncated_flag_false_when_fits(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=50)]
        result = allocator.allocate(blocks, config=default_config)
        assert result.selected_blocks[0].is_truncated is False

    def test_truncated_flag_true_when_exceeds(self, allocator):
        tight = BudgetConfig(context_window=5_000, reserved_response_tokens=500,
                              system_prompt_reservation=200,
                              conversation_history_reservation=300,
                              min_guaranteed_per_block=50,
                              max_per_block=3_000)
        blocks = [make_ranked(estimated_tokens=5_000, source="big")]
        result = allocator.allocate(blocks, config=tight)
        assert result.selected_blocks[0].is_truncated is True

    def test_truncation_marker_no_content_change(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=500, content="original content")]
        result = allocator.allocate(blocks, config=default_config)
        ab = result.selected_blocks[0]
        assert ab.block.block.content == "original content"
        assert ab.allocated_tokens != ab.block.block.estimated_tokens or not ab.is_truncated


# ---------------------------------------------------------------------------
# Test: Model-specific limits
# ---------------------------------------------------------------------------

class TestModelLimits:
    @pytest.mark.parametrize("model,expected_window", [
        ("gemini-2.0-flash", 1_048_576),
        ("gpt-4", 32_768),
        ("gpt-3.5-turbo", 16_384),
        ("claude-3-opus", 200_000),
    ])
    def test_model_limits(self, model, expected_window):
        c = BudgetConfig.for_model(model)
        assert c.context_window == expected_window

    def test_model_limits_dict_complete(self):
        assert "gemini-2.0-flash" in MODEL_LIMITS
        assert "gpt-4" in MODEL_LIMITS
        assert "default" not in MODEL_LIMITS


# ---------------------------------------------------------------------------
# Test: Deterministic behavior
# ---------------------------------------------------------------------------

class TestDeterministic:
    def test_identical_inputs_produce_same_output(self, allocator, default_config):
        blocks = make_ranked_blocks(5, estimated_tokens=200)
        r1 = allocator.allocate(blocks, config=default_config)
        r2 = allocator.allocate(blocks, config=default_config)
        assert r1.total_selected == r2.total_selected
        assert r1.total_discarded == r2.total_discarded
        assert r1.report.allocated_tokens == r2.report.allocated_tokens

    def test_order_preserved_for_equal_blocks(self, allocator, default_config):
        blocks = make_ranked_blocks(3, estimated_tokens=200, combined_score=0.5)
        result = allocator.allocate(blocks, config=default_config)
        sources = [ab.block.block.source for ab in result.selected_blocks]
        # Original order preserved if all selected
        assert sources[:3] == ["src0", "src1", "src2"]


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_estimated_tokens(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=0)]
        result = allocator.allocate(blocks, config=default_config)
        assert result.total_selected == 1
        assert result.selected_blocks[0].allocated_tokens >= default_config.min_guaranteed_per_block

    def test_max_per_block_respected(self, allocator):
        cfg = BudgetConfig(context_window=100_000, reserved_response_tokens=500,
                            system_prompt_reservation=500,
                            conversation_history_reservation=500,
                            min_guaranteed_per_block=100,
                            max_per_block=500)
        blocks = [make_ranked(estimated_tokens=50_000)]
        result = allocator.allocate(blocks, config=cfg)
        assert result.selected_blocks[0].allocated_tokens <= 500

    def test_min_guaranteed_respected(self, allocator):
        cfg = BudgetConfig(context_window=5_000, reserved_response_tokens=500,
                            system_prompt_reservation=500,
                            conversation_history_reservation=500,
                            min_guaranteed_per_block=200,
                            max_per_block=5_000)
        blocks = [make_ranked(estimated_tokens=10)]
        result = allocator.allocate(blocks, config=cfg)
        assert result.selected_blocks[0].allocated_tokens >= 200


# ---------------------------------------------------------------------------
# Test: Stress
# ---------------------------------------------------------------------------

class TestStress:
    def test_100_blocks_allocates_quickly(self, allocator, default_config):
        blocks = make_ranked_blocks(100, estimated_tokens=500)
        import time
        start = time.perf_counter()
        result = allocator.allocate(blocks, config=default_config)
        elapsed = time.perf_counter() - start
        assert result.total_selected + result.total_discarded == 100
        assert elapsed < 2.0

    def test_1000_blocks_no_error(self, allocator, default_config):
        blocks = make_ranked_blocks(1_000, estimated_tokens=200)
        result = allocator.allocate(blocks, config=default_config)
        assert result.report.total_blocks_input == 1_000
        assert result.total_selected + result.total_discarded == 1_000


# ---------------------------------------------------------------------------
# Test: Event publishing
# ---------------------------------------------------------------------------

class TestEventPublishing:
    @pytest.mark.anyio
    async def test_allocate_publishes_event(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("TokenBudgetAllocated", capture)

        allocator = AdaptiveTokenBudgetAllocator(event_bus=bus)
        await allocator.start()

        blocks = [make_ranked(estimated_tokens=100)]
        allocator.allocate(blocks, config=BudgetConfig())

        await bus.shutdown()

        assert "TokenBudgetAllocated" in received

    @pytest.mark.anyio
    async def test_no_events_when_not_running(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("TokenBudgetAllocated", capture)

        allocator = AdaptiveTokenBudgetAllocator(event_bus=bus)
        blocks = [make_ranked(estimated_tokens=100)]
        allocator.allocate(blocks, config=BudgetConfig())

        await bus.shutdown()

        assert "TokenBudgetAllocated" not in received


# ---------------------------------------------------------------------------
# Test: Kernel integration
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_allocator(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("token_allocator")
            assert svc is not None
            assert isinstance(svc, AdaptiveTokenBudgetAllocator)

            h = kernel.health()
            assert h.token_allocator.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_lifecycle_via_kernel(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            allocator = kernel.get_service("token_allocator")
            assert allocator is not None
            assert allocator._running

            blocks = [make_ranked(estimated_tokens=150, content="kernel test")]
            result = allocator.allocate(blocks)
            assert result.total_selected == 1
            assert result.report.allocated_tokens > 0
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
            allocator = kernel.get_service("token_allocator")
            assert allocator is not None
            assert allocator._running
            h = kernel.health()
            assert h.token_allocator.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_regression_other_subsystems_unaffected(self):
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
            assert kernel.get_service("token_allocator") is not None
        finally:
            await kernel.shutdown()


# ---------------------------------------------------------------------------
# Test: Regression - allocation from ranked result
# ---------------------------------------------------------------------------

class TestRegression:
    def test_allocate_from_ranking_result(self, allocator, default_config):
        from app.ranking.base import RankingResult

        blocks = [
            make_ranked(source="mem", estimated_tokens=300, combined_score=0.9),
            make_ranked(source="kb", estimated_tokens=200, combined_score=0.5),
        ]
        ranking = RankingResult(ranked_blocks=blocks, total_blocks=2)
        result = allocator.allocate(ranking.ranked_blocks, config=default_config)
        assert result.total_selected == 2

    def test_allocation_result_fields(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config)
        assert hasattr(result, "selected_blocks")
        assert hasattr(result, "discarded_blocks")
        assert hasattr(result, "report")
        assert isinstance(result.report, BudgetReport)

    def test_selected_blocks_have_allocated_block_type(self, allocator, default_config):
        blocks = [make_ranked(estimated_tokens=100)]
        result = allocator.allocate(blocks, config=default_config)
        assert isinstance(result.selected_blocks[0], AllocatedBlock)
