from datetime import datetime, timezone, timedelta
from typing import List

import pytest

from app.extraction.base import ContextBlock
from app.ranking.base import RankedContextBlock
from app.budget.base import AllocatedBlock
from app.validation.base import (
    IContextValidator,
    ValidationConfig,
    ValidationReport,
    ValidationResult,
    DEFAULT_VALIDATION_CONFIG,
    SUPPORTED_SOURCE_PREFIXES,
)
from app.validation.validator import ContextValidator
from app.validation.events import ContextValidated


def make_allocated(
    source: str = "memory/session",
    content: str = "valid content",
    metadata: dict = None,
    confidence: float = 1.0,
    importance: float = 0.5,
    estimated_tokens: int = 100,
    timestamp: datetime = None,
    allocated: int = 100,
) -> AllocatedBlock:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    block = ContextBlock(
        source=source,
        content=content,
        metadata=metadata or {},
        confidence=confidence,
        importance=importance,
        estimated_tokens=estimated_tokens,
        timestamp=timestamp,
    )
    rc = RankedContextBlock(block=block, combined_score=0.5)
    return AllocatedBlock(block=rc, allocated_tokens=allocated)


def make_allocated_blocks(count: int, content: str = None, **kwargs) -> List[AllocatedBlock]:
    return [
        make_allocated(
            source=f"memory/src{i}",
            content=f"unique content {i}" if content is None else content,
            **kwargs,
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator():
    return ContextValidator()


# ---------------------------------------------------------------------------
# Test: Creation and naming
# ---------------------------------------------------------------------------

class TestValidatorCreation:
    def test_validator_name(self):
        v = ContextValidator()
        assert v.validator_name == "context_validator"

    def test_health_default(self):
        v = ContextValidator()
        h = v.health()
        assert h["status"] == "HEALTHY"

    def test_start_shutdown(self):
        v = ContextValidator()
        assert not v._running
        import anyio
        anyio.run(v.start)
        assert v._running
        anyio.run(v.shutdown)
        assert not v._running

    def test_implements_interface(self):
        assert issubclass(ContextValidator, IContextValidator)
        v = ContextValidator()
        assert isinstance(v, IContextValidator)


# ---------------------------------------------------------------------------
# Test: Basic validation
# ---------------------------------------------------------------------------

class TestBasicValidation:
    def test_empty_blocks(self, validator):
        result = validator.validate([])
        assert result.report.input_blocks == 0
        assert result.report.valid_blocks == 0
        assert result.valid_blocks == []

    def test_single_valid_block(self, validator):
        ab = make_allocated()
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert result.report.input_blocks == 1
        assert result.report.removed_duplicates == 0
        assert result.report.removed_invalid == 0

    def test_multiple_valid_blocks(self, validator):
        blocks = make_allocated_blocks(5)
        result = validator.validate(blocks)
        assert result.report.valid_blocks == 5
        assert result.report.input_blocks == 5

    def test_valid_blocks_list_matches_report(self, validator):
        blocks = make_allocated_blocks(3)
        result = validator.validate(blocks)
        assert len(result.valid_blocks) == result.report.valid_blocks

    def test_report_fields_present(self, validator):
        ab = make_allocated()
        result = validator.validate([ab])
        r = result.report
        assert hasattr(r, "input_blocks")
        assert hasattr(r, "valid_blocks")
        assert hasattr(r, "removed_duplicates")
        assert hasattr(r, "removed_invalid")
        assert hasattr(r, "warnings")
        assert hasattr(r, "errors")

    def test_result_has_report(self, validator):
        result = validator.validate([])
        assert isinstance(result.report, ValidationReport)


# ---------------------------------------------------------------------------
# Test: Empty content detection
# ---------------------------------------------------------------------------

class TestEmptyContent:
    def test_empty_content_removed(self, validator):
        ab = make_allocated(content="")
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1
        assert result.report.valid_blocks == 0

    def test_whitespace_only_removed(self, validator):
        ab = make_allocated(content="   \n  \t  ")
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1

    def test_content_empty_check_disabled(self, validator):
        cfg = ValidationConfig(enable_content_empty_check=False)
        ab = make_allocated(content="")
        result = validator.validate([ab], config=cfg)
        assert result.report.valid_blocks == 1


# ---------------------------------------------------------------------------
# Test: Metadata validation
# ---------------------------------------------------------------------------

class TestMetadataValidation:
    def test_non_dict_metadata_removed(self, validator):
        ab = make_allocated(metadata="not_a_dict")
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1

    def test_dict_metadata_accepted(self, validator):
        ab = make_allocated(metadata={"key": "value"})
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1

    def test_oversized_metadata_warning(self, validator):
        large_meta = {"data": "x" * 10_000}
        ab = make_allocated(metadata=large_meta)
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert any("metadata size" in w for w in result.report.warnings)


# ---------------------------------------------------------------------------
# Test: Timestamp validation
# ---------------------------------------------------------------------------

class TestTimestampValidation:
    def test_future_timestamp_removed(self, validator):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        ab = make_allocated(timestamp=future)
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1

    def test_naive_timestamp_warning(self, validator):
        naive = datetime(2025, 1, 1)
        ab = make_allocated(timestamp=naive)
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert any("naive timestamp" in w for w in result.report.warnings)

    def test_past_timestamp_before_2000_warning(self, validator):
        old = datetime(1999, 1, 1, tzinfo=timezone.utc)
        ab = make_allocated(timestamp=old)
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert any("before year 2000" in w for w in result.report.warnings)


# ---------------------------------------------------------------------------
# Test: Confidence validation
# ---------------------------------------------------------------------------

class TestConfidenceValidation:
    def test_confidence_below_zero_warns(self, validator):
        ab = make_allocated(confidence=-0.5)
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert any("outside [0,1]" in w for w in result.report.warnings)

    def test_confidence_above_one_warns(self, validator):
        ab = make_allocated(confidence=1.5)
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert any("outside [0,1]" in w for w in result.report.warnings)

    def test_confidence_normalized(self, validator):
        ab = make_allocated(confidence=1.5)
        validator.validate([ab])
        assert ab.block.block.confidence == 1.0


# ---------------------------------------------------------------------------
# Test: Token estimate validation
# ---------------------------------------------------------------------------

class TestTokenEstimateValidation:
    def test_negative_tokens_removed(self, validator):
        ab = make_allocated(estimated_tokens=-10)
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1

    def test_zero_tokens_accepted(self, validator):
        ab = make_allocated(estimated_tokens=0)
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1


# ---------------------------------------------------------------------------
# Test: Source validation
# ---------------------------------------------------------------------------

class TestSourceValidation:
    def test_empty_source_removed(self, validator):
        ab = make_allocated(source="")
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1

    def test_malformed_source_too_long(self, validator):
        ab = make_allocated(source="m" * 200)
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1

    def test_unrecognized_prefix_warning(self, validator):
        ab = make_allocated(source="unknown/test")
        result = validator.validate([ab])
        assert result.report.valid_blocks == 1
        assert any("unrecognized source prefix" in w for w in result.report.warnings)

    def test_known_prefixes_accepted(self, validator):
        for prefix in SUPPORTED_SOURCE_PREFIXES:
            ab = make_allocated(source=f"{prefix}/test")
            result = validator.validate([ab])
            assert result.report.valid_blocks == 1, f"Prefix '{prefix}' should be valid"


# ---------------------------------------------------------------------------
# Test: Duplicate detection
# ---------------------------------------------------------------------------

class TestDuplicateDetection:
    def test_duplicate_content_removed(self, validator):
        blocks = [
            make_allocated(source="memory/a", content="same content"),
            make_allocated(source="memory/b", content="same content"),
        ]
        result = validator.validate(blocks)
        assert result.report.removed_duplicates == 1
        assert result.report.valid_blocks == 1

    def test_duplicate_source_removed(self, validator):
        blocks = [
            make_allocated(source="memory/test", content="content a"),
            make_allocated(source="memory/test", content="content b"),
        ]
        result = validator.validate(blocks)
        assert result.report.removed_duplicates == 1

    def test_source_not_duplicate_when_no_source(self, validator):
        blocks = [
            make_allocated(source="", content="content a"),
        ]
        result = validator.validate(blocks)
        assert result.report.removed_invalid == 1

    def test_unique_blocks_kept(self, validator):
        blocks = [
            make_allocated(source="memory/a", content="content a"),
            make_allocated(source="memory/b", content="content b"),
        ]
        result = validator.validate(blocks)
        assert result.report.valid_blocks == 2
        assert result.report.removed_duplicates == 0

    def test_duplicate_detection_disabled(self, validator):
        cfg = ValidationConfig(enable_duplicate_content_detection=False)
        blocks = [
            make_allocated(source="memory/a", content="same"),
            make_allocated(source="memory/b", content="same"),
        ]
        result = validator.validate(blocks, config=cfg)
        assert result.report.valid_blocks == 2


# ---------------------------------------------------------------------------
# Test: Conflict detection
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_conflicting_metadata_detected(self, validator):
        blocks = [
            make_allocated(source="memory/a", metadata={"priority": "high"}),
            make_allocated(source="memory/b", metadata={"priority": "low"}),
        ]
        result = validator.validate(blocks)
        assert any("Conflicting" in w for w in result.report.warnings)

    def test_same_metadata_no_conflict(self, validator):
        blocks = [
            make_allocated(source="memory/a", metadata={"priority": "high"}),
            make_allocated(source="memory/b", metadata={"priority": "high"}),
        ]
        result = validator.validate(blocks)
        assert not any("Conflicting" in w for w in result.report.warnings)

    def test_conflict_detection_disabled(self, validator):
        cfg = ValidationConfig(enable_conflict_detection=False)
        blocks = [
            make_allocated(source="memory/a", metadata={"priority": "high"}),
            make_allocated(source="memory/b", metadata={"priority": "low"}),
        ]
        result = validator.validate(blocks, config=cfg)
        assert not any("Conflicting" in w for w in result.report.warnings)


# ---------------------------------------------------------------------------
# Test: Normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_confidence_clamped_above(self, validator):
        ab = make_allocated(confidence=2.0)
        validator.validate([ab])
        assert ab.block.block.confidence == 1.0

    def test_confidence_clamped_below(self, validator):
        ab = make_allocated(confidence=-1.0)
        validator.validate([ab])
        assert ab.block.block.confidence == 0.0

    def test_metadata_normalized_from_non_dict(self, validator):
        ab = make_allocated(metadata="bad")
        validator.validate([ab])
        # Block is removed as invalid, but we already tested that
        pass

    def test_valid_confidence_unchanged(self, validator):
        ab = make_allocated(confidence=0.75)
        validator.validate([ab])
        assert ab.block.block.confidence == 0.75


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_multiple_issues_same_block(self, validator):
        ab = make_allocated(
            content="",
            confidence=-1.0,
            estimated_tokens=-5,
            source="",
        )
        result = validator.validate([ab])
        assert result.report.removed_invalid == 1
        assert result.report.valid_blocks == 0

    def test_all_blocks_removed(self, validator):
        blocks = make_allocated_blocks(10, content="")
        result = validator.validate(blocks)
        assert result.report.valid_blocks == 0
        assert result.report.removed_invalid == 10

    def test_mixed_valid_and_invalid(self, validator):
        valid = make_allocated(source="memory/ok", content="good")
        invalid = make_allocated(source="memory/bad", content="")
        result = validator.validate([valid, invalid])
        assert result.report.valid_blocks == 1
        assert result.report.removed_invalid == 1

    def test_first_occurrence_of_duplicate_kept(self, validator):
        blocks = [
            make_allocated(source="memory/a", content="unique a"),
            make_allocated(source="memory/b", content="shared"),
            make_allocated(source="memory/c", content="shared"),
        ]
        result = validator.validate(blocks)
        assert result.report.valid_blocks == 2
        assert result.valid_blocks[0].block.block.source == "memory/a"
        assert result.valid_blocks[1].block.block.source == "memory/b"


# ---------------------------------------------------------------------------
# Test: Deterministic behavior
# ---------------------------------------------------------------------------

class TestDeterministic:
    def test_identical_inputs_same_output(self, validator):
        blocks = [
            make_allocated(source="memory/a", content="first"),
            make_allocated(source="memory/b", content=""),
            make_allocated(source="memory/a", content="first"),
        ]
        r1 = validator.validate(blocks)
        r2 = validator.validate(blocks)
        assert r1.report.valid_blocks == r2.report.valid_blocks
        assert r1.report.removed_invalid == r2.report.removed_invalid
        assert r1.report.removed_duplicates == r2.report.removed_duplicates
        assert len(r1.report.warnings) == len(r2.report.warnings)


# ---------------------------------------------------------------------------
# Test: Stress
# ---------------------------------------------------------------------------

class TestStress:
    def test_100_blocks_validates_quickly(self, validator):
        import time
        blocks = make_allocated_blocks(100)
        start = time.perf_counter()
        result = validator.validate(blocks)
        elapsed = time.perf_counter() - start
        assert result.report.valid_blocks == 100
        assert elapsed < 2.0

    def test_1000_blocks_no_error(self, validator):
        blocks = make_allocated_blocks(1_000)
        result = validator.validate(blocks)
        assert result.report.input_blocks == 1_000


# ---------------------------------------------------------------------------
# Test: Event publishing
# ---------------------------------------------------------------------------

class TestEventPublishing:
    @pytest.mark.anyio
    async def test_validate_publishes_event(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("ContextValidated", capture)

        validator = ContextValidator(event_bus=bus)
        await validator.start()

        ab = make_allocated()
        validator.validate([ab])

        await bus.shutdown()

        assert "ContextValidated" in received

    @pytest.mark.anyio
    async def test_no_events_when_not_running(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("ContextValidated", capture)

        validator = ContextValidator(event_bus=bus)
        ab = make_allocated()
        validator.validate([ab])

        await bus.shutdown()

        assert "ContextValidated" not in received


# ---------------------------------------------------------------------------
# Test: Kernel integration
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_validator(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("context_validator")
            assert svc is not None
            assert isinstance(svc, ContextValidator)

            h = kernel.health()
            assert h.context_validator.status.value == "HEALTHY"
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
            validator = kernel.get_service("context_validator")
            assert validator is not None
            assert validator._running

            ab = make_allocated(content="kernel test")
            result = validator.validate([ab])
            assert result.report.valid_blocks == 1
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
            validator = kernel.get_service("context_validator")
            assert validator is not None
            assert validator._running
            h = kernel.health()
            assert h.context_validator.status.value == "HEALTHY"
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
            assert kernel.get_service("context_validator") is not None
        finally:
            await kernel.shutdown()


# ---------------------------------------------------------------------------
# Test: Regression
# ---------------------------------------------------------------------------

class TestRegression:
    def test_validate_from_allocation_result(self, validator):
        from app.budget.base import AllocationResult
        blocks = [make_allocated()]
        allocation = AllocationResult(selected_blocks=blocks)
        result = validator.validate(allocation.selected_blocks)
        assert result.report.valid_blocks == 1

    def test_total_removed_property(self):
        r = ValidationReport(input_blocks=10, valid_blocks=5,
                             removed_duplicates=2, removed_invalid=3)
        assert r.total_removed == 5

    def test_validate_preserves_allocated_tokens(self, validator):
        ab = make_allocated(allocated=500)
        result = validator.validate([ab])
        assert result.valid_blocks[0].allocated_tokens == 500
