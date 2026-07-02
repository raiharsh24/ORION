from datetime import datetime, timezone

import pytest

from app.extraction.base import ContextBlock
from app.ranking.base import RankedContextBlock
from app.budget.base import AllocatedBlock
from app.compression.base import (
    IContextCompressor,
    CompressionPolicy,
    CompressedBlock,
    CompressionReport,
    CompressionResult,
    DEFAULT_COMPRESSION_POLICY,
)
from app.compression.compressor import ContextCompressor, _estimate_tokens
from app.compression.events import ContextCompressed


def make_allocated(
    source: str = "memory/session",
    content: str = "valid content for testing",
    estimated_tokens: int = 0,
) -> AllocatedBlock:
    block = ContextBlock(
        source=source,
        content=content,
        estimated_tokens=estimated_tokens or max(1, len(content) // 4),
        timestamp=datetime.now(timezone.utc),
    )
    return AllocatedBlock(
        block=RankedContextBlock(block=block, combined_score=0.5),
        allocated_tokens=500,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def compressor():
    return ContextCompressor()


@pytest.fixture
def sample_block():
    return make_allocated()


# ---------------------------------------------------------------------------
# Test: Creation and naming
# ---------------------------------------------------------------------------

class TestCompressorCreation:
    def test_compressor_name(self):
        c = ContextCompressor()
        assert c.compressor_name == "context_compressor"

    def test_health_default(self):
        c = ContextCompressor()
        h = c.health()
        assert h["status"] == "HEALTHY"

    def test_start_shutdown(self):
        c = ContextCompressor()
        assert not c._running
        import anyio
        anyio.run(c.start)
        assert c._running
        anyio.run(c.shutdown)
        assert not c._running

    def test_implements_interface(self):
        assert issubclass(ContextCompressor, IContextCompressor)
        assert isinstance(ContextCompressor(), IContextCompressor)


# ---------------------------------------------------------------------------
# Test: Token estimator
# ---------------------------------------------------------------------------

class TestTokenEstimator:
    def test_estimates_tokens(self):
        assert _estimate_tokens("hello world") == 2

    def test_minimum_one(self):
        assert _estimate_tokens("") == 1

    def test_long_text(self):
        text = "word " * 100
        expected = len(text) // 4
        assert _estimate_tokens(text) == expected


# ---------------------------------------------------------------------------
# Test: NONE policy
# ---------------------------------------------------------------------------

class TestNonePolicy:
    def test_none_returns_original(self, compressor, sample_block):
        result = compressor.compress([sample_block], policy=CompressionPolicy.NONE)
        assert len(result.compressed_blocks) == 1
        cb = result.compressed_blocks[0]
        assert cb.original_tokens == cb.compressed_tokens
        assert cb.policy_applied == "none"
        assert cb.compression_ratio == 0.0

    def test_none_report(self, compressor):
        blocks = [make_allocated(content="a"), make_allocated(content="b")]
        result = compressor.compress(blocks, policy=CompressionPolicy.NONE)
        assert result.report.saved_tokens == 0
        assert result.report.compression_ratio == 0.0


# ---------------------------------------------------------------------------
# Test: LIGHT policy
# ---------------------------------------------------------------------------

class TestLightPolicy:
    def test_light_removes_trailing_whitespace(self, compressor):
        ab = make_allocated(content="line 1  \nline 2  \nline 3")
        result = compressor.compress([ab], policy=CompressionPolicy.LIGHT)
        content = result.compressed_blocks[0].block.block.block.content
        for line in content.split("\n"):
            assert line == line.rstrip()

    def test_light_collapses_excess_blank_lines(self, compressor):
        ab = make_allocated(content="a\n\n\n\n\n\nb")
        result = compressor.compress([ab], policy=CompressionPolicy.LIGHT)
        content = result.compressed_blocks[0].block.block.block.content
        assert content.count("\n") < 5  # was 6 newlines, now at most 3

    def test_light_preserves_single_blank(self, compressor):
        ab = make_allocated(content="a\n\nb")
        result = compressor.compress([ab], policy=CompressionPolicy.LIGHT)
        content = result.compressed_blocks[0].block.block.block.content
        assert "a\n\nb" in content or content == "a\n\nb"

    def test_light_reduces_tokens(self, compressor):
        ab = make_allocated(content="  hello  \n\n\n\n  world  ")
        result = compressor.compress([ab], policy=CompressionPolicy.LIGHT)
        cb = result.compressed_blocks[0]
        assert cb.compressed_tokens <= cb.original_tokens


# ---------------------------------------------------------------------------
# Test: STANDARD policy
# ---------------------------------------------------------------------------

class TestStandardPolicy:
    def test_standard_removes_redundant_lines(self, compressor):
        ab = make_allocated(content="same\nsame\ndifferent")
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        content = result.compressed_blocks[0].block.block.block.content
        assert content.count("same") == 1

    def test_standard_removes_repeated_sentences(self, compressor):
        text = "Hello world. This is a test. Hello world. Goodbye."
        ab = make_allocated(content=text)
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        content = result.compressed_blocks[0].block.block.block.content
        assert content.count("Hello world") == 1

    def test_standard_collapses_horizontal_rules(self, compressor):
        text = "a\n---\n---\n---\nb"
        ab = make_allocated(content=text)
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        content = result.compressed_blocks[0].block.block.block.content
        assert content.count("---") == 1

    def test_standard_reduces_tokens(self, compressor):
        ab = make_allocated(
            content="word " * 50 + "\nword " * 50 + "\nunique ending"
        )
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        cb = result.compressed_blocks[0]
        assert cb.compressed_tokens < cb.original_tokens


# ---------------------------------------------------------------------------
# Test: AGGRESSIVE policy
# ---------------------------------------------------------------------------

class TestAggressivePolicy:
    def test_aggressive_shortens_stack_trace(self, compressor):
        trace = "\n".join(
            [f'  File "code.py", line {i}, in func{i}' for i in range(20)]
        )
        ab = make_allocated(source="terminal/output", content=trace)
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        content = result.compressed_blocks[0].block.block.block.content
        lines = content.strip().split("\n")
        assert len(lines) < 10

    def test_aggressive_collapses_logs(self, compressor):
        logs = "\n".join(
            [f"2026-01-01 12:00:{i:02d} INFO same message" for i in range(10)]
        )
        ab = make_allocated(source="terminal/output", content=logs)
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        content = result.compressed_blocks[0].block.block.block.content
        assert "repeated" in content

    def test_aggressive_trims_code_comments(self, compressor):
        code = (
            "def foo():\n"
            "    # this is a comment\n"
            "    x = 1\n"
            "    # another comment\n"
            "    return x\n"
        )
        ab = make_allocated(source="memory/code", content=code)
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        content = result.compressed_blocks[0].block.block.block.content
        assert "#" not in content

    def test_aggressive_trims_code_blank_lines(self, compressor):
        code = "```python\ndef foo():\n\n\n\n    pass\n```"
        ab = make_allocated(source="memory/code", content=code)
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        content = result.compressed_blocks[0].block.block.block.content
        assert "\n\n" not in content.replace("```", "")

    def test_aggressive_preserves_code_block_markers(self, compressor):
        code = "```python\ndef foo():\n    pass\n```"
        ab = make_allocated(source="memory/code", content=code)
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        content = result.compressed_blocks[0].block.block.block.content
        assert "```" in content
        assert "def foo()" in content


# ---------------------------------------------------------------------------
# Test: Skip logic
# ---------------------------------------------------------------------------

class TestSkipLogic:
    def test_system_prompt_skipped(self, compressor):
        ab = make_allocated(source="system/prompt", content="You are a helpful AI.")
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        cb = result.compressed_blocks[0]
        assert cb.policy_applied == "skipped"
        assert cb.block.block.block.content == "You are a helpful AI."

    def test_user_prompt_skipped(self, compressor):
        ab = make_allocated(source="user/query", content="What is the weather?")
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        assert result.compressed_blocks[0].policy_applied == "skipped"

    def test_json_content_skipped(self, compressor):
        ab = make_allocated(source="memory/data", content='{"key": "value"}')
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        assert result.compressed_blocks[0].policy_applied == "skipped"
        assert result.compressed_blocks[0].block.block.block.content == '{"key": "value"}'

    def test_xml_content_skipped(self, compressor):
        ab = make_allocated(source="memory/data", content="<root><item>val</item></root>")
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        assert result.compressed_blocks[0].policy_applied == "skipped"

    def test_yaml_content_skipped(self, compressor):
        ab = make_allocated(source="memory/data", content="- key: value\n  nested: true")
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        assert result.compressed_blocks[0].policy_applied == "skipped"

    def test_empty_content_skipped(self, compressor):
        ab = make_allocated(content="")
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        assert result.compressed_blocks[0].policy_applied == "skipped"


# ---------------------------------------------------------------------------
# Test: Compression report
# ---------------------------------------------------------------------------

class TestCompressionReport:
    def test_report_has_all_fields(self, compressor):
        ab = make_allocated(content="hello world")
        result = compressor.compress([ab])
        r = result.report
        assert hasattr(r, "input_tokens")
        assert hasattr(r, "output_tokens")
        assert hasattr(r, "saved_tokens")
        assert hasattr(r, "compression_ratio")
        assert hasattr(r, "per_block_statistics")
        assert hasattr(r, "skipped_blocks")
        assert hasattr(r, "warnings")

    def test_report_aggregates_tokens(self, compressor):
        blocks = [
            make_allocated(content="hello " * 20),
            make_allocated(content="world " * 20),
        ]
        result = compressor.compress(blocks, policy=CompressionPolicy.STANDARD)
        assert result.report.input_tokens >= result.report.output_tokens
        assert result.report.saved_tokens >= 0

    def test_report_has_per_block_stats(self, compressor):
        ab = make_allocated(content="hello world")
        result = compressor.compress([ab])
        assert len(result.report.per_block_statistics) == 1
        stat = result.report.per_block_statistics[0]
        assert "source" in stat
        assert "original_tokens" in stat
        assert "compressed_tokens" in stat
        assert "ratio" in stat
        assert "policy" in stat

    def test_report_skipped_blocks_counted(self, compressor):
        blocks = [
            make_allocated(source="system/prompt", content="don't touch"),
            make_allocated(source="memory/data", content="compress me"),
        ]
        result = compressor.compress(blocks, policy=CompressionPolicy.AGGRESSIVE)
        assert result.report.skipped_blocks == 1

    def test_no_compression_report(self, compressor):
        result = compressor.compress([], policy=CompressionPolicy.NONE)
        assert result.report.input_tokens == 0
        assert result.report.compression_ratio == 0.0


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_blocks_list(self, compressor):
        result = compressor.compress([])
        assert len(result.compressed_blocks) == 0
        assert result.report.input_tokens == 0

    def test_already_minimal_content(self, compressor):
        ab = make_allocated(content="short")
        result = compressor.compress([ab], policy=CompressionPolicy.AGGRESSIVE)
        cb = result.compressed_blocks[0]
        assert cb.block.block.block.content == "short"

    def test_content_expansion_warning(self, compressor):
        ab = make_allocated(content="a")
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        # "a" is already minimal, compression shouldn't expand meaningfully
        cb = result.compressed_blocks[0]
        assert cb.compressed_tokens >= 1

    def test_multiple_blocks_mixed_compression(self, compressor):
        blocks = [
            make_allocated(source="system/prompt", content="keep"),
            make_allocated(content="  redundant\n\n\n\n  redundant\n"),
        ]
        result = compressor.compress(blocks, policy=CompressionPolicy.LIGHT)
        assert result.report.skipped_blocks == 1
        assert len(result.compressed_blocks) == 2

    def test_compressed_block_fields(self, compressor):
        ab = make_allocated(content="some content here")
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        cb = result.compressed_blocks[0]
        assert isinstance(cb, CompressedBlock)
        assert cb.original_tokens > 0
        assert isinstance(cb.compression_ratio, float)
        assert cb.estimated_savings >= 0

    def test_policy_enum_values(self):
        assert CompressionPolicy.NONE.value == "none"
        assert CompressionPolicy.LIGHT.value == "light"
        assert CompressionPolicy.STANDARD.value == "standard"
        assert CompressionPolicy.AGGRESSIVE.value == "aggressive"


# ---------------------------------------------------------------------------
# Test: Deterministic behavior
# ---------------------------------------------------------------------------

class TestDeterministic:
    def test_identical_inputs_same_output(self, compressor):
        text = "line 1\n\n\n\nline 2\nline 2\nline 3"
        ab = make_allocated(content=text)
        r1 = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        r2 = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        assert (r1.compressed_blocks[0].block.block.block.content
                == r2.compressed_blocks[0].block.block.block.content)
        assert r1.report.compression_ratio == r2.report.compression_ratio

    def test_order_preserved(self, compressor):
        ab1 = make_allocated(source="memory/a", content="first")
        ab2 = make_allocated(source="memory/b", content="second")
        result = compressor.compress([ab1, ab2], policy=CompressionPolicy.STANDARD)
        sources = [cb.block.block.block.source for cb in result.compressed_blocks]
        assert sources == ["memory/a", "memory/b"]


# ---------------------------------------------------------------------------
# Test: CompressedBlock post_init
# ---------------------------------------------------------------------------

class TestCompressedBlockPostInit:
    def test_compression_ratio_computed(self):
        cb = CompressedBlock(
            block=make_allocated(),
            original_tokens=100,
            compressed_tokens=60,
        )
        assert cb.compression_ratio == 0.4
        assert cb.estimated_savings == 40

    def test_zero_original_tokens(self):
        cb = CompressedBlock(
            block=make_allocated(),
            original_tokens=0,
            compressed_tokens=0,
        )
        assert cb.compression_ratio == 0.0
        assert cb.estimated_savings == 0


# ---------------------------------------------------------------------------
# Test: Stress
# ---------------------------------------------------------------------------

class TestStress:
    def test_100_blocks_compresses_quickly(self, compressor):
        import time
        blocks = [make_allocated(content=f"block {i} content with some " * 10) for i in range(100)]
        start = time.perf_counter()
        result = compressor.compress(blocks, policy=CompressionPolicy.AGGRESSIVE)
        elapsed = time.perf_counter() - start
        assert len(result.compressed_blocks) == 100
        assert elapsed < 2.0

    def test_1000_blocks_no_error(self, compressor):
        blocks = [make_allocated(content=f"content {i}") for i in range(1000)]
        result = compressor.compress(blocks, policy=CompressionPolicy.STANDARD)
        assert len(result.compressed_blocks) == 1000


# ---------------------------------------------------------------------------
# Test: Event publishing
# ---------------------------------------------------------------------------

class TestEventPublishing:
    @pytest.mark.anyio
    async def test_compress_publishes_event(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("ContextCompressed", capture)

        compressor = ContextCompressor(event_bus=bus)
        await compressor.start()

        ab = make_allocated(content="test content")
        compressor.compress([ab])

        await bus.shutdown()

        assert "ContextCompressed" in received

    @pytest.mark.anyio
    async def test_no_events_when_not_running(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("ContextCompressed", capture)

        compressor = ContextCompressor(event_bus=bus)
        ab = make_allocated()
        compressor.compress([ab])

        await bus.shutdown()

        assert "ContextCompressed" not in received


# ---------------------------------------------------------------------------
# Test: Kernel integration
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_compressor(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("context_compressor")
            assert svc is not None
            assert isinstance(svc, ContextCompressor)

            h = kernel.health()
            assert h.context_compressor.status.value == "HEALTHY"
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
            compressor = kernel.get_service("context_compressor")
            assert compressor is not None
            assert compressor._running

            ab = make_allocated(content="  spaced  \n\n\n  text  ")
            result = compressor.compress([ab], policy=CompressionPolicy.LIGHT)
            assert len(result.compressed_blocks) == 1
            assert result.report.saved_tokens >= 0
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
            compressor = kernel.get_service("context_compressor")
            assert compressor is not None
            assert compressor._running
            h = kernel.health()
            assert h.context_compressor.status.value == "HEALTHY"
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
            assert kernel.get_service("context_compressor") is not None
        finally:
            await kernel.shutdown()


# ---------------------------------------------------------------------------
# Test: Regression
# ---------------------------------------------------------------------------

class TestRegression:
    def test_compress_from_validation_result(self, compressor):
        from app.validation.base import ValidationResult
        ab = make_allocated(content="validated block content")
        validation = ValidationResult(valid_blocks=[ab])
        result = compressor.compress(validation.valid_blocks, policy=CompressionPolicy.STANDARD)
        assert len(result.compressed_blocks) == 1
        assert result.report.saved_tokens >= 0

    def test_content_never_expands_significantly(self, compressor):
        text = "short"
        ab = make_allocated(content=text)
        for policy in CompressionPolicy:
            result = compressor.compress([ab], policy=policy)
            cb = result.compressed_blocks[0]
            compression_ratio = cb.original_tokens - cb.compressed_tokens
            assert compression_ratio >= -2, f"Policy {policy} expanded content"

    def test_compressed_content_still_readable(self, compressor):
        text = "The quick brown fox jumps over the lazy dog."
        ab = make_allocated(content=text)
        result = compressor.compress([ab], policy=CompressionPolicy.STANDARD)
        content = result.compressed_blocks[0].block.block.block.content
        assert "quick" in content
        assert "fox" in content
