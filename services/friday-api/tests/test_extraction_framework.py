import pytest
import asyncio
from typing import List

from app.extraction.base import IContextExtractor, ContextBlock, ExtractionResult
from app.extraction.events import (
    ContextExtractionStarted,
    ContextExtractionCompleted,
    ContextExtractionFailed,
)
from app.extraction.extractors import (
    MemoryExtractor, KnowledgeExtractor, WorkflowExtractor,
    DesktopExtractor, BrowserExtractor, TerminalExtractor,
    MissionExtractor, VoiceExtractor, SystemStateExtractor,
)
from app.extraction.registry import ExtractorRegistry
from app.context.base import StrategyConfig, TokenBudget
from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.kernel import FridayKernel, FridayKernelConfig


# ----------------------------------------------------------------
# Unit Tests: ContextBlock & ExtractionResult
# ----------------------------------------------------------------

class TestContextBlock:
    def test_defaults(self):
        b = ContextBlock()
        assert b.source == ""
        assert b.title == ""
        assert b.content == ""
        assert b.metadata == {}
        assert b.confidence == 1.0
        assert b.importance == 0.5
        assert b.estimated_tokens == 0

    def test_custom_values(self):
        b = ContextBlock(
            source="test/source",
            title="Test Block",
            content="hello world",
            metadata={"key": "val"},
            confidence=0.8,
            importance=0.9,
            estimated_tokens=50,
        )
        assert b.source == "test/source"
        assert b.title == "Test Block"
        assert b.content == "hello world"
        assert b.metadata == {"key": "val"}
        assert b.confidence == 0.8
        assert b.importance == 0.9
        assert b.estimated_tokens == 50

    def test_timestamp_is_datetime(self):
        b = ContextBlock()
        from datetime import datetime
        assert isinstance(b.timestamp, datetime)


class TestExtractionResult:
    def test_empty(self):
        r = ExtractionResult()
        assert r.blocks == []
        assert r.failures == []
        assert r.success_count == 0
        assert r.failure_count == 0
        assert r.total_estimated_tokens == 0

    def test_with_blocks(self):
        b1 = ContextBlock(content="a", estimated_tokens=10)
        b2 = ContextBlock(content="b", estimated_tokens=20)
        r = ExtractionResult(blocks=[b1, b2], failures=["err"])
        assert r.success_count == 2
        assert r.failure_count == 1
        assert r.total_estimated_tokens == 30

    def test_only_failures(self):
        r = ExtractionResult(failures=["e1", "e2"])
        assert r.success_count == 0
        assert r.failure_count == 2
        assert r.total_estimated_tokens == 0


# ----------------------------------------------------------------
# Unit Tests: IContextExtractor interface
# ----------------------------------------------------------------

class TestIContextExtractor:
    """Verifies that the ABC rejects direct instantiation."""

    def test_abc_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            IContextExtractor()


# ----------------------------------------------------------------
# Unit Tests: All 9 Concrete Extractors
# ----------------------------------------------------------------

class TestConcreteExtractors:
    @pytest.mark.parametrize("ext_cls,expected_name", [
        (MemoryExtractor, "memory_extractor"),
        (KnowledgeExtractor, "knowledge_extractor"),
        (WorkflowExtractor, "workflow_extractor"),
        (DesktopExtractor, "desktop_extractor"),
        (BrowserExtractor, "browser_extractor"),
        (TerminalExtractor, "terminal_extractor"),
        (MissionExtractor, "mission_extractor"),
        (VoiceExtractor, "voice_extractor"),
        (SystemStateExtractor, "system_state_extractor"),
    ])
    def test_extractor_name(self, ext_cls, expected_name):
        assert ext_cls.extractor_name == expected_name

    @pytest.mark.parametrize("ext_cls", [
        MemoryExtractor, KnowledgeExtractor, WorkflowExtractor,
        DesktopExtractor, BrowserExtractor, TerminalExtractor,
        MissionExtractor, VoiceExtractor, SystemStateExtractor,
    ])
    def test_supported_sources_non_empty(self, ext_cls):
        e = ext_cls()
        assert len(e.supported_sources) >= 1

    @pytest.mark.parametrize("ext_cls", [
        MemoryExtractor, KnowledgeExtractor, WorkflowExtractor,
        DesktopExtractor, BrowserExtractor, TerminalExtractor,
        MissionExtractor, VoiceExtractor, SystemStateExtractor,
    ])
    def test_priority_positive(self, ext_cls):
        e = ext_cls()
        assert e.priority > 0

    @pytest.mark.anyio
    @pytest.mark.parametrize("ext_cls", [
        MemoryExtractor, KnowledgeExtractor, WorkflowExtractor,
        DesktopExtractor, BrowserExtractor, TerminalExtractor,
        MissionExtractor, VoiceExtractor, SystemStateExtractor,
    ])
    async def test_extract_returns_blocks(self, ext_cls):
        e = ext_cls()
        blocks = await e.extract("test request")
        assert isinstance(blocks, list)
        assert len(blocks) >= 1
        for b in blocks:
            assert isinstance(b, ContextBlock)
            assert b.source
            assert b.title
            assert b.content
            assert b.estimated_tokens > 0

    @pytest.mark.anyio
    async def test_all_extractors_concurrently(self):
        extractors = [
            MemoryExtractor(), KnowledgeExtractor(), WorkflowExtractor(),
            DesktopExtractor(), BrowserExtractor(), TerminalExtractor(),
            MissionExtractor(), VoiceExtractor(), SystemStateExtractor(),
        ]
        results = await asyncio.gather(*[e.extract("test") for e in extractors])
        assert len(results) == 9
        all_blocks = [b for blocks in results for b in blocks]
        assert len(all_blocks) == 9  # one block per extractor


# ----------------------------------------------------------------
# Unit Tests: ExtractorRegistry
# ----------------------------------------------------------------

class SlowExtractor(IContextExtractor):
    extractor_name = "slow_extractor"
    supported_sources = ["test"]
    priority = 999

    async def extract(self, request: str) -> List[ContextBlock]:
        await asyncio.sleep(0.5)
        return [ContextBlock(source="slow", title="Slow", content="done")]


class FailingExtractor(IContextExtractor):
    extractor_name = "failing_extractor"
    supported_sources = ["test"]
    priority = 1

    async def extract(self, request: str) -> List[ContextBlock]:
        raise RuntimeError("Intentional failure for testing")


class TestExtractorRegistryUnit:
    def make_registry(self):
        return ExtractorRegistry()

    def test_init_empty(self):
        r = self.make_registry()
        assert len(r._extractors) == 0

    def test_register_and_get(self):
        r = self.make_registry()
        ext = MemoryExtractor()
        r.register(ext)
        assert r.get("memory_extractor") is ext
        assert r.get("nonexistent") is None

    def test_register_multiple(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        r.register(KnowledgeExtractor())
        r.register(TerminalExtractor())
        assert len(r._extractors) == 3

    def test_unregister(self):
        r = self.make_registry()
        ext = MemoryExtractor()
        r.register(ext)
        assert "memory_extractor" in r._extractors
        r.unregister("memory_extractor")
        assert "memory_extractor" not in r._extractors

    def test_list_extractors(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        r.register(DesktopExtractor())
        listing = r.list_extractors()
        assert "memory_extractor" in listing
        assert "desktop_extractor" in listing
        assert listing["memory_extractor"] == 10

    def test_resolve_by_strategy(self):
        r = self.make_registry()
        mem = MemoryExtractor()
        knw = KnowledgeExtractor()
        r.register(mem)
        r.register(knw)
        config = StrategyConfig(extractors=["memory_extractor", "knowledge_extractor"])
        resolved = r.resolve_by_strategy(config)
        assert len(resolved) == 2
        assert resolved[0] is mem  # priority 10
        assert resolved[1] is knw  # priority 20

    def test_resolve_by_strategy_skips_missing(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        config = StrategyConfig(extractors=["memory_extractor", "nonexistent_extractor"])
        resolved = r.resolve_by_strategy(config)
        assert len(resolved) == 1

    def test_resolve_by_strategy_empty(self):
        r = self.make_registry()
        config = StrategyConfig(extractors=[])
        resolved = r.resolve_by_strategy(config)
        assert resolved == []

    def test_lifecycle_start_shutdown(self):
        r = self.make_registry()
        import anyio
        anyio.run(r.start)
        assert r._running is True
        anyio.run(r.shutdown)
        assert r._running is False

    def test_health(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        r.register(DesktopExtractor())
        h = r.health()
        assert h["status"] == "HEALTHY"
        assert h["details"]["registered_extractors"] == 2

    @pytest.mark.anyio
    async def test_extract_all_with_no_extractors(self):
        r = self.make_registry()
        result = await r.extract_all("test")
        assert result.failures == ["No extractors registered"]
        assert result.blocks == []

    @pytest.mark.anyio
    async def test_extract_all_returns_all_blocks(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        r.register(KnowledgeExtractor())
        r.register(TerminalExtractor())
        await r.start()
        result = await r.extract_all("hello")
        assert len(result.blocks) == 3
        assert result.failures == []
        await r.shutdown()

    @pytest.mark.anyio
    async def test_extract_all_returns_sorted_by_priority(self):
        r = self.make_registry()
        r.register(DesktopExtractor())  # priority 40
        r.register(MemoryExtractor())   # priority 10
        await r.start()
        result = await r.extract_all("test")
        assert len(result.blocks) == 2
        # MemoryExtractor (priority 10) before DesktopExtractor (priority 40)
        assert result.blocks[0].source == "memory/session"
        assert result.blocks[1].source == "desktop/controller"
        await r.shutdown()

    @pytest.mark.anyio
    async def test_handle_failing_extractor(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        r.register(FailingExtractor())
        r.register(TerminalExtractor())
        await r.start()
        result = await r.extract_all("test")
        # Should have 2 successful blocks and 1 failure
        assert len(result.blocks) == 2
        assert len(result.failures) == 1
        assert "failing_extractor" in result.failures[0]
        await r.shutdown()

    @pytest.mark.anyio
    async def test_all_failing_returns_failure(self):
        r = self.make_registry()
        r.register(FailingExtractor())
        await r.start()
        result = await r.extract_all("test")
        assert result.blocks == []
        assert len(result.failures) == 1
        await r.shutdown()

    @pytest.mark.anyio
    async def test_timeout_protection(self):
        r = self.make_registry()
        ext = SlowExtractor()
        r.register(ext)
        await r.start()
        result = await r.extract_all("test", timeout=0.1)
        assert len(result.blocks) == 0
        assert len(result.failures) == 1
        assert "timed out" in result.failures[0].lower()
        await r.shutdown()

    @pytest.mark.anyio
    async def test_extract_for_strategy(self):
        r = self.make_registry()
        mem = MemoryExtractor()
        trm = TerminalExtractor()
        r.register(mem)
        r.register(trm)
        await r.start()

        config = StrategyConfig(extractors=["memory_extractor", "terminal_extractor"])
        result = await r.extract_for_strategy("run tests", config)
        assert len(result.blocks) == 2
        assert result.failures == []
        await r.shutdown()

    @pytest.mark.anyio
    async def test_extract_for_strategy_empty_config(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        await r.start()
        config = StrategyConfig(extractors=[])
        result = await r.extract_for_strategy("test", config)
        assert result.failures == ["No extractors resolved for strategy"]
        await r.shutdown()

    @pytest.mark.anyio
    async def test_extract_for_strategy_missing_extractors(self):
        r = self.make_registry()
        config = StrategyConfig(extractors=["nonexistent"])
        result = await r.extract_for_strategy("test", config)
        assert result.failures == ["No extractors resolved for strategy"]

    @pytest.mark.anyio
    async def test_concurrent_extraction_all(self):
        r = self.make_registry()
        r.register(MemoryExtractor())
        r.register(KnowledgeExtractor())
        r.register(TerminalExtractor())
        r.register(DesktopExtractor())
        r.register(BrowserExtractor())
        await r.start()
        result = await r.extract_all("concurrent test")
        assert len(result.blocks) == 5
        await r.shutdown()

    @pytest.mark.anyio
    async def test_no_event_bus_does_not_crash(self):
        r = ExtractorRegistry(event_bus=None)
        r.register(MemoryExtractor())
        await r.start()
        result = await r.extract_all("test")
        assert len(result.blocks) == 1
        await r.shutdown()


# ----------------------------------------------------------------
# Integration Tests: EventBus events
# ----------------------------------------------------------------

class TestExtractorEventBusIntegration:
    @pytest.mark.anyio
    async def test_publishes_extraction_started(self):
        bus = EventBus()
        r = ExtractorRegistry(event_bus=bus)
        r.register(MemoryExtractor())
        r.register(TerminalExtractor())
        await r.start()

        received = []
        bus.subscribe("ContextExtractionStarted", lambda e: received.append(e))

        await r.extract_all("hello")

        assert len(received) == 1
        event = received[0]
        assert isinstance(event, ContextExtractionStarted)
        assert event.topic == "ContextExtractionStarted"
        assert "memory_extractor" in event.data["extractor_names"]
        assert "terminal_extractor" in event.data["extractor_names"]

        await r.shutdown()

    @pytest.mark.anyio
    async def test_publishes_extraction_completed(self):
        bus = EventBus()
        r = ExtractorRegistry(event_bus=bus)
        r.register(MemoryExtractor())
        r.register(KnowledgeExtractor())
        await r.start()

        completed = []
        bus.subscribe("ContextExtractionCompleted", lambda e: completed.append(e))

        await r.extract_all("search query")

        assert len(completed) == 1
        event = completed[0]
        assert isinstance(event, ContextExtractionCompleted)
        assert event.topic == "ContextExtractionCompleted"
        assert event.data["block_count"] == 2
        assert event.data["total_tokens"] > 0
        assert event.data["partial_failures"] == []

        await r.shutdown()

    @pytest.mark.anyio
    async def test_publishes_extraction_failed_on_all_fail(self):
        bus = EventBus()
        r = ExtractorRegistry(event_bus=bus)
        r.register(FailingExtractor())
        await r.start()

        failed = []
        bus.subscribe("ContextExtractionFailed", lambda e: failed.append(e))

        await r.extract_all("test")

        assert len(failed) == 1
        event = failed[0]
        assert isinstance(event, ContextExtractionFailed)
        assert event.topic == "ContextExtractionFailed"
        assert "failing_extractor" in event.data["error"]

        await r.shutdown()

    @pytest.mark.anyio
    async def test_partial_failure_still_completes(self):
        bus = EventBus()
        r = ExtractorRegistry(event_bus=bus)
        r.register(MemoryExtractor())
        r.register(FailingExtractor())
        await r.start()

        completed = []
        bus.subscribe("ContextExtractionCompleted", lambda e: completed.append(e))

        await r.extract_all("test")

        assert len(completed) == 1
        event = completed[0]
        assert event.data["block_count"] == 1
        assert len(event.data["partial_failures"]) == 1

        await r.shutdown()

    @pytest.mark.anyio
    async def test_extract_for_strategy_publishes_events(self):
        bus = EventBus()
        r = ExtractorRegistry(event_bus=bus)
        r.register(MemoryExtractor())
        r.register(TerminalExtractor())
        await r.start()

        started = []
        completed = []
        bus.subscribe("ContextExtractionStarted", lambda e: started.append(e))
        bus.subscribe("ContextExtractionCompleted", lambda e: completed.append(e))

        config = StrategyConfig(extractors=["memory_extractor", "terminal_extractor"])
        result = await r.extract_for_strategy("test", config)

        assert len(started) == 1
        assert len(completed) == 1
        assert result.success_count == 2

        await r.shutdown()

    @pytest.mark.anyio
    async def test_no_events_when_not_running(self):
        bus = EventBus()
        r = ExtractorRegistry(event_bus=bus)
        r.register(MemoryExtractor())
        # Not started

        received = []
        bus.subscribe("ContextExtractionStarted", lambda e: received.append(e))

        result = await r.extract_all("test")
        assert len(result.blocks) == 1
        # No event should be published because _running is False
        assert len(received) == 0


# ----------------------------------------------------------------
# Regression Tests: Kernel
# ----------------------------------------------------------------

class TestExtractorKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_extractor_registry(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("extractor_registry")
            assert svc is not None
            assert isinstance(svc, ExtractorRegistry)

            h = kernel.health()
            assert h.extractor_registry.status.value == "HEALTHY"
            assert h.extractor_registry.details["registered_extractors"] == 10
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_lifecycle_via_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            reg = kernel.get_service("extractor_registry")
            assert reg._running is True
            assert len(reg._extractors) == 10

            reg_from_module = kernel.module_registry.get_module("extractor_registry")
            assert reg_from_module is reg
        finally:
            await kernel.shutdown()

        assert reg._running is False

    @pytest.mark.anyio
    async def test_extraction_through_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            reg = kernel.get_service("extractor_registry")
            result = await reg.extract_all("test request through kernel")
            assert result.success_count >= 10
            assert result.failure_count == 0

            # Verify variety of sources
            sources = {b.source for b in result.blocks}
            assert "memory/session" in sources
            assert "knowledge/base" in sources
            assert "workflow/engine" in sources
            assert "desktop/controller" in sources
            assert "browser/state" in sources
            assert "terminal/session" in sources
            assert "missions/manager" in sources
            assert "voice/manager" in sources
            assert "system/state" in sources
            assert "desktop_intelligence/windows" in sources
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_extract_for_strategy_through_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            reg = kernel.get_service("extractor_registry")
            strategy_mgr = kernel.get_service("strategy_manager")

            from app.intent.types import IntentType
            strategy = strategy_mgr.get_strategy(IntentType.CODING)
            config = strategy.get_config()

            result = await reg.extract_for_strategy("write a sorting algorithm", config)
            assert result.success_count >= 1
            assert result.failure_count == 0
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_event_flow_through_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            event_bus = kernel.get_service("event_bus")
            reg = kernel.get_service("extractor_registry")

            started = []
            completed = []
            event_bus.subscribe("ContextExtractionStarted", lambda e: started.append(e))
            event_bus.subscribe("ContextExtractionCompleted", lambda e: completed.append(e))

            await reg.extract_all("end-to-end test")

            assert len(started) == 1
            assert len(completed) == 1
            assert completed[0].data["block_count"] >= 10
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_kernel_restart(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()
        svc1 = kernel.get_service("extractor_registry")
        await kernel.shutdown()

        await kernel.boot()
        svc2 = kernel.get_service("extractor_registry")
        assert svc2 is not None
        assert isinstance(svc2, ExtractorRegistry)
        assert svc2 is not svc1
        assert svc2._running is True
        assert len(svc2._extractors) == 10
        await kernel.shutdown()

    @pytest.mark.anyio
    async def test_stress_sequential_extractions(self):
        """Stress test: 20 sequential extract_all calls to verify no resource leaks."""
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            reg = kernel.get_service("extractor_registry")
            for i in range(20):
                result = await reg.extract_all(f"stress test iteration {i}")
                assert result.success_count >= 10
                assert result.failure_count == 0
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_stress_concurrent_extractions(self):
        """Stress test: 10 concurrent extract_all calls."""
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            reg = kernel.get_service("extractor_registry")
            tasks = [reg.extract_all(f"concurrent stress {i}") for i in range(10)]
            results = await asyncio.gather(*tasks)
            for result in results:
                assert result.success_count >= 10
                assert result.failure_count == 0
        finally:
            await kernel.shutdown()
