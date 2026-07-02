from datetime import datetime, timezone

import pytest

from app.extraction.base import ContextBlock
from app.ranking.base import RankedContextBlock
from app.budget.base import AllocatedBlock, BudgetReport
from app.compression.base import CompressedBlock, CompressionReport
from app.assembly.base import (
    IContextAssembler,
    PromptSection,
    PromptFormat,
    PromptFrame,
    PromptReport,
    AssemblyResult,
    SECTION_ORDER,
    GEMINI_FORMAT,
    OPENAI_FORMAT,
    ANTHROPIC_FORMAT,
    LOCAL_FORMAT,
    PROVIDER_FORMATS,
    source_to_section,
)
from app.assembly.templates import build_frame
from app.assembly.assembler import PromptAssembler
from app.assembly.events import PromptAssembled


def make_compressed(
    source: str = "memory/session",
    content: str = "test content",
    compressed_tokens: int = 0,
    is_truncated: bool = False,
) -> CompressedBlock:
    block = ContextBlock(
        source=source,
        content=content,
        estimated_tokens=max(1, len(content) // 4),
        timestamp=datetime.now(timezone.utc),
    )
    rc = RankedContextBlock(block=block, combined_score=0.5)
    ab = AllocatedBlock(block=rc, allocated_tokens=500, is_truncated=is_truncated)
    ct = compressed_tokens or max(1, len(content) // 4)
    return CompressedBlock(block=ab, original_tokens=ct, compressed_tokens=ct)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def assembler():
    return PromptAssembler()


# ---------------------------------------------------------------------------
# Test: Creation and naming
# ---------------------------------------------------------------------------

class TestAssemblerCreation:
    def test_assembler_name(self):
        a = PromptAssembler()
        assert a.assembler_name == "prompt_assembler"

    def test_health_default(self):
        a = PromptAssembler()
        h = a.health()
        assert h["status"] == "HEALTHY"

    def test_start_shutdown(self):
        a = PromptAssembler()
        assert not a._running
        import anyio
        anyio.run(a.start)
        assert a._running
        anyio.run(a.shutdown)
        assert not a._running

    def test_implements_interface(self):
        assert issubclass(PromptAssembler, IContextAssembler)
        assert isinstance(PromptAssembler(), IContextAssembler)


# ---------------------------------------------------------------------------
# Test: source_to_section mapping
# ---------------------------------------------------------------------------

class TestSourceToSection:
    def test_system_maps_to_system_prompt(self):
        assert source_to_section("system/prompt") == "system_prompt"

    def test_memory_maps_to_long_term_memory(self):
        assert source_to_section("memory/session") == "long_term_memory"

    def test_knowledge_maps_to_retrieved_knowledge(self):
        assert source_to_section("knowledge/doc") == "retrieved_knowledge"

    def test_workflow_maps_to_workflow_state(self):
        assert source_to_section("workflow/active") == "workflow_state"

    def test_desktop_maps_to_desktop_context(self):
        assert source_to_section("desktop/window") == "desktop_context"

    def test_browser_maps_to_desktop_context(self):
        assert source_to_section("browser/tab") == "desktop_context"

    def test_terminal_maps_to_desktop_context(self):
        assert source_to_section("terminal/output") == "desktop_context"

    def test_mission_maps_to_workflow_state(self):
        assert source_to_section("mission/active") == "workflow_state"

    def test_voice_maps_to_conversation_history(self):
        assert source_to_section("voice/input") == "conversation_history"

    def test_user_maps_to_user_query(self):
        assert source_to_section("user/query") == "user_query"

    def test_unknown_prefix_maps_to_retrieved_knowledge(self):
        assert source_to_section("unknown/thing") == "retrieved_knowledge"

    def test_no_prefix_maps_to_retrieved_knowledge(self):
        assert source_to_section("raw") == "retrieved_knowledge"


# ---------------------------------------------------------------------------
# Test: Basic assembly
# ---------------------------------------------------------------------------

class TestBasicAssembly:
    def test_empty_blocks(self, assembler):
        result = assembler.assemble([])
        assert result.report.prompt_tokens == 0
        assert len(result.report.omitted_sections) == 8

    def test_single_block(self, assembler):
        cb = make_compressed(source="memory/session", content="memory data")
        result = assembler.assemble([cb])
        assert result.frame is not None
        assert len(result.frame.sections) == 8

    def test_blocks_sorted_by_section_order(self, assembler):
        blocks = [
            make_compressed(source="user/query", content="user question"),
            make_compressed(source="system/prompt", content="system instruction"),
        ]
        result = assembler.assemble(blocks)
        names = [s.name for s in result.frame.sections if not s.is_omitted]
        assert names[0] == "system_prompt"
        assert names[-1] == "user_query"

    def test_report_fields_present(self, assembler):
        cb = make_compressed(content="test")
        result = assembler.assemble([cb])
        r = result.report
        assert hasattr(r, "prompt_tokens")
        assert hasattr(r, "section_sizes")
        assert hasattr(r, "omitted_sections")
        assert hasattr(r, "truncation_flags")
        assert hasattr(r, "provider")
        assert hasattr(r, "template_name")


# ---------------------------------------------------------------------------
# Test: Gemini provider format
# ---------------------------------------------------------------------------

class TestGeminiFormat:
    def test_gemini_messages_have_parts(self, assembler):
        cb = make_compressed(source="memory/session", content="memory content")
        result = assembler.assemble([cb], provider="gemini")
        frame = result.frame
        assert frame.messages
        for msg in frame.messages:
            assert "role" in msg
            assert "parts" in msg

    def test_gemini_system_instruction(self, assembler):
        cb = make_compressed(source="system/prompt", content="you are a bot")
        result = assembler.assemble([cb], provider="gemini")
        assert "you are a bot" in result.frame.system_instruction

    def test_gemini_user_query(self, assembler):
        cb = make_compressed(source="user/query", content="hello")
        result = assembler.assemble([cb], provider="gemini")
        assert any("hello" in str(m) for m in result.frame.messages)

    def test_gemini_role_user(self, assembler):
        cb = make_compressed(source="memory/session", content="data")
        result = assembler.assemble([cb], provider="gemini")
        assert result.frame.messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# Test: OpenAI provider format
# ---------------------------------------------------------------------------

class TestOpenAIFormat:
    def test_openai_messages_have_content(self, assembler):
        cb = make_compressed(source="memory/session", content="memory data")
        result = assembler.assemble([cb], provider="openai")
        frame = result.frame
        assert frame.messages
        for msg in frame.messages:
            assert "role" in msg
            assert "content" in msg

    def test_openai_system_as_message(self, assembler):
        cb = make_compressed(source="system/prompt", content="you are helpful")
        result = assembler.assemble([cb], provider="openai")
        msgs = result.frame.messages
        assert any(m["role"] == "system" for m in msgs)

    def test_openai_user_role(self, assembler):
        cb = make_compressed(source="memory/session", content="data")
        result = assembler.assemble([cb], provider="openai")
        assert result.frame.messages[-1]["role"] == "user"


# ---------------------------------------------------------------------------
# Test: Anthropic provider format
# ---------------------------------------------------------------------------

class TestAnthropicFormat:
    def test_anthropic_system_instruction(self, assembler):
        cb = make_compressed(source="system/prompt", content="be helpful")
        result = assembler.assemble([cb], provider="anthropic")
        assert "be helpful" in result.frame.system_instruction

    def test_anthropic_user_role(self, assembler):
        cb = make_compressed(source="memory/session", content="data")
        result = assembler.assemble([cb], provider="anthropic")
        assert result.frame.messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# Test: Local provider format
# ---------------------------------------------------------------------------

class TestLocalFormat:
    def test_local_text_prompt(self, assembler):
        cb = make_compressed(source="memory/session", content="data")
        result = assembler.assemble([cb], provider="local")
        assert result.frame.text_prompt
        assert "Long Term Memory" in result.frame.text_prompt or "###" in result.frame.text_prompt

    def test_local_no_messages(self, assembler):
        cb = make_compressed(source="memory/session", content="data")
        result = assembler.assemble([cb], provider="local")
        assert not result.frame.messages

    def test_local_system_section(self, assembler):
        cb = make_compressed(source="system/prompt", content="be a bot")
        result = assembler.assemble([cb], provider="local")
        assert "### System" in result.frame.text_prompt


# ---------------------------------------------------------------------------
# Test: Provider constant formats
# ---------------------------------------------------------------------------

class TestProviderFormats:
    def test_gemini_format(self):
        assert GEMINI_FORMAT.provider == "gemini"
        assert GEMINI_FORMAT.role_assistant == "model"

    def test_openai_format(self):
        assert OPENAI_FORMAT.provider == "openai"
        assert OPENAI_FORMAT.role_assistant == "assistant"

    def test_anthropic_format(self):
        assert ANTHROPIC_FORMAT.provider == "anthropic"
        assert ANTHROPIC_FORMAT.role_assistant == "assistant"

    def test_local_format(self):
        assert LOCAL_FORMAT.provider == "local"
        assert not LOCAL_FORMAT.use_json_messages

    def test_provider_formats_dict(self):
        assert "gemini" in PROVIDER_FORMATS
        assert "openai" in PROVIDER_FORMATS
        assert "anthropic" in PROVIDER_FORMATS
        assert "local" in PROVIDER_FORMATS

    def test_section_order_complete(self):
        expected = [
            "system_prompt", "conversation_history", "long_term_memory",
            "retrieved_knowledge", "workflow_state", "desktop_context",
            "tool_context", "user_query",
        ]
        assert SECTION_ORDER == expected


# ---------------------------------------------------------------------------
# Test: Token budget enforcement
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def test_budget_respected(self, assembler):
        budget = BudgetReport(allocated_tokens=10)
        cb = make_compressed(source="memory/session", content="x" * 200)
        result = assembler.assemble([cb], budget_report=budget)
        assert result.report.prompt_tokens <= 10

    def test_budget_omits_excess_sections(self, assembler):
        budget = BudgetReport(allocated_tokens=5)
        blocks = [
            make_compressed(source="system/prompt", content="long system prompt " * 20),
            make_compressed(source="memory/session", content="some memory"),
        ]
        result = assembler.assemble(blocks, budget_report=budget)
        assert result.report.prompt_tokens <= 5

    def test_no_budget_all(self, assembler):
        cb = make_compressed(source="memory/session", content="data")
        result = assembler.assemble([cb])
        assert result.report.prompt_tokens > 0

    def test_truncation_flags_set(self, assembler):
        budget = BudgetReport(allocated_tokens=5)
        cb = make_compressed(source="memory/session", content="hello world " * 20)
        result = assembler.assemble([cb], budget_report=budget)
        assert result.report.truncation_flags.get("long_term_memory") is True


# ---------------------------------------------------------------------------
# Test: Prompt frames and sections
# ---------------------------------------------------------------------------

class TestPromptFrames:
    def test_sections_follow_order(self, assembler):
        blocks = [
            make_compressed(source="user/query", content="q"),
            make_compressed(source="system/prompt", content="s"),
            make_compressed(source="memory/session", content="m"),
        ]
        result = assembler.assemble(blocks)
        names = [s.name for s in result.frame.sections if not s.is_omitted]
        assert names == ["system_prompt", "long_term_memory", "user_query"]

    def test_section_tokens_counted(self, assembler):
        cb = make_compressed(source="memory/session", content="hello world")
        result = assembler.assemble([cb])
        section = next(s for s in result.frame.sections if s.name == "long_term_memory")
        assert section.tokens > 0
        assert section.content == "hello world"

    def test_build_frame_direct(self):
        sections = [
            PromptSection(name="system_prompt", content="sys", tokens=1),
            PromptSection(name="user_query", content="usr", tokens=1),
        ]
        frame = build_frame(sections, provider="gemini")
        assert frame.system_instruction == "sys"
        assert frame.messages

    def test_empty_section_omitted(self, assembler):
        result = assembler.assemble([])
        assert result.frame.sections[0].is_omitted
        assert result.frame.sections[0].name == "system_prompt"


# ---------------------------------------------------------------------------
# Test: Deterministic
# ---------------------------------------------------------------------------

class TestDeterministic:
    def test_identical_inputs_same_output(self, assembler):
        cb = make_compressed(source="memory/session", content="stable content")
        r1 = assembler.assemble([cb])
        r2 = assembler.assemble([cb])
        assert r1.report.prompt_tokens == r2.report.prompt_tokens
        assert r1.report.omitted_sections == r2.report.omitted_sections

    def test_order_preserved(self, assembler):
        cb = make_compressed(source="memory/session", content="test")
        result = assembler.assemble([cb])
        names = [s.name for s in result.frame.sections]
        assert names == SECTION_ORDER


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_blocks_with_empty_content_skipped(self, assembler):
        cb = make_compressed(source="memory/session", content="")
        result = assembler.assemble([cb])
        assert "long_term_memory" in result.report.omitted_sections

    def test_all_sections_present_even_if_empty(self, assembler):
        result = assembler.assemble([])
        assert len(result.frame.sections) == 8
        assert all(s.is_omitted for s in result.frame.sections)

    def test_multiple_blocks_same_section(self, assembler):
        blocks = [
            make_compressed(source="memory/a", content="first"),
            make_compressed(source="memory/b", content="second"),
        ]
        result = assembler.assemble(blocks)
        section = next(s for s in result.frame.sections if s.name == "long_term_memory")
        assert "first" in section.content
        assert "second" in section.content


# ---------------------------------------------------------------------------
# Test: Stress
# ---------------------------------------------------------------------------

class TestStress:
    def test_100_blocks_assembles_quickly(self, assembler):
        import time
        blocks = [
            make_compressed(source=f"memory/src{i}", content=f"block {i} content " * 5)
            for i in range(100)
        ]
        start = time.perf_counter()
        result = assembler.assemble(blocks)
        elapsed = time.perf_counter() - start
        assert result.frame is not None
        assert elapsed < 2.0

    def test_1000_blocks_no_error(self, assembler):
        blocks = [
            make_compressed(source=f"memory/src{i}", content=f"content {i}")
            for i in range(1000)
        ]
        result = assembler.assemble(blocks)
        assert result.report.prompt_tokens > 0


# ---------------------------------------------------------------------------
# Test: Event publishing
# ---------------------------------------------------------------------------

class TestEventPublishing:
    @pytest.mark.anyio
    async def test_assemble_publishes_event(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("PromptAssembled", capture)

        assembler = PromptAssembler(event_bus=bus)
        await assembler.start()

        cb = make_compressed(content="test")
        assembler.assemble([cb])

        await bus.shutdown()

        assert "PromptAssembled" in received

    @pytest.mark.anyio
    async def test_no_events_when_not_running(self):
        from app.events.bus import EventBus
        bus = EventBus()
        received = []

        async def capture(event):
            received.append(event.topic)

        bus.subscribe("PromptAssembled", capture)

        assembler = PromptAssembler(event_bus=bus)
        cb = make_compressed()
        assembler.assemble([cb])

        await bus.shutdown()

        assert "PromptAssembled" not in received


# ---------------------------------------------------------------------------
# Test: Kernel integration
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_assembler(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig

        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("prompt_assembler")
            assert svc is not None
            assert isinstance(svc, PromptAssembler)

            h = kernel.health()
            assert h.prompt_assembler.status.value == "HEALTHY"
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
            pa = kernel.get_service("prompt_assembler")
            assert pa is not None
            assert pa._running

            cb = make_compressed(content="kernel test")
            result = pa.assemble([cb])
            assert result.frame is not None
            assert result.report.prompt_tokens > 0
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
            pa = kernel.get_service("prompt_assembler")
            assert pa is not None
            assert pa._running
            h = kernel.health()
            assert h.prompt_assembler.status.value == "HEALTHY"
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
            assert kernel.get_service("prompt_assembler") is not None
        finally:
            await kernel.shutdown()


# ---------------------------------------------------------------------------
# Test: Regression
# ---------------------------------------------------------------------------

class TestRegression:
    def test_full_pipeline_round_trip(self, assembler):
        cb = make_compressed(source="system/prompt", content="be helpful",
                             compressed_tokens=10)
        result = assembler.assemble([cb], provider="gemini")
        assert "be helpful" in result.frame.system_instruction
        assert result.report.provider == "gemini"

    def test_content_not_modified(self, assembler):
        original = "original content here"
        cb = make_compressed(source="memory/session", content=original)
        assembler.assemble([cb])
        assert cb.block.block.block.content == original

    def test_report_is_assembly_result(self, assembler):
        cb = make_compressed(content="test")
        result = assembler.assemble([cb])
        assert isinstance(result, AssemblyResult)
        assert isinstance(result.report, PromptReport)
        assert isinstance(result.frame, PromptFrame)
