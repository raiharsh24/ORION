import pytest
from typing import List, Optional

from app.intent.types import IntentType
from app.intent.analyzer import IntentResult
from app.intent.events import IntentAnalyzed
from app.events.bus import EventBus
from app.context.base import (
    ContextStrategy, StrategyConfig, TokenBudget,
    RetrievalPriority, CompressionPolicy, CachePolicy,
)
from app.context.strategies import (
    ConversationStrategy, CodingStrategy, TerminalStrategy,
    DesktopStrategy, BrowserStrategy, WorkflowStrategy,
    PlanningStrategy, MemoryStrategy, SearchStrategy,
    VisionStrategy, UnknownStrategy,
)
from app.context.manager import StrategyManager
from app.context.events import StrategyResolved
from app.kernel import FridayKernel, FridayKernelConfig


# ----------------------------------------------------------------
# Unit Tests: Data Classes
# ----------------------------------------------------------------

class TestDataClasses:
    def test_token_budget_defaults(self):
        b = TokenBudget()
        assert b.total == 4096
        assert b.system == 512
        assert b.reserved == 512

    def test_token_budget_custom(self):
        b = TokenBudget(total=8192, system=1024, retrieved_context=4096)
        assert b.total == 8192
        assert b.system == 1024
        assert b.retrieved_context == 4096
        assert b.conversation_history == 1024  # default

    def test_retrieval_priority_defaults(self):
        r = RetrievalPriority()
        assert len(r.sources) == 5
        assert r.sources[0] == "working_memory"
        assert r.sources[-1] == "knowledge_base"

    def test_retrieval_priority_custom(self):
        r = RetrievalPriority(sources=["a", "b"])
        assert r.sources == ["a", "b"]

    def test_compression_policy_defaults(self):
        c = CompressionPolicy()
        assert c.strategy == "summarize"
        assert c.max_tokens == 2048
        assert c.threshold == 0.8

    def test_cache_policy_defaults(self):
        c = CachePolicy()
        assert c.ttl_seconds == 120
        assert c.max_entries == 100
        assert c.invalidation == "lru"

    def test_strategy_config_defaults(self):
        sc = StrategyConfig()
        assert sc.extractors == []
        assert isinstance(sc.token_budget, TokenBudget)
        assert isinstance(sc.retrieval_priority, RetrievalPriority)
        assert isinstance(sc.compression_policy, CompressionPolicy)
        assert isinstance(sc.cache_policy, CachePolicy)

    def test_strategy_config_custom_extractors(self):
        sc = StrategyConfig(extractors=["a", "b", "c"])
        assert sc.extractors == ["a", "b", "c"]


# ----------------------------------------------------------------
# Unit Tests: All 11 Strategies
# ----------------------------------------------------------------

class TestAllStrategies:
    @pytest.mark.parametrize("strategy_cls,intent", [
        (ConversationStrategy, IntentType.CONVERSATION),
        (CodingStrategy, IntentType.CODING),
        (TerminalStrategy, IntentType.TERMINAL),
        (DesktopStrategy, IntentType.DESKTOP),
        (BrowserStrategy, IntentType.BROWSER),
        (WorkflowStrategy, IntentType.WORKFLOW),
        (PlanningStrategy, IntentType.PLANNING),
        (MemoryStrategy, IntentType.MEMORY),
        (SearchStrategy, IntentType.SEARCH),
        (VisionStrategy, IntentType.VISION),
        (UnknownStrategy, IntentType.UNKNOWN),
    ])
    def test_intent_type_matches(self, strategy_cls, intent):
        s = strategy_cls()
        assert s.intent_type == intent

    @pytest.mark.parametrize("strategy_cls", [
        ConversationStrategy, CodingStrategy, TerminalStrategy,
        DesktopStrategy, BrowserStrategy, WorkflowStrategy,
        PlanningStrategy, MemoryStrategy, SearchStrategy,
        VisionStrategy, UnknownStrategy,
    ])
    def test_config_is_not_none(self, strategy_cls):
        s = strategy_cls()
        config = s.get_config()
        assert config is not None
        assert isinstance(config, StrategyConfig)

    @pytest.mark.parametrize("strategy_cls", [
        ConversationStrategy, CodingStrategy, TerminalStrategy,
        DesktopStrategy, BrowserStrategy, WorkflowStrategy,
        PlanningStrategy, MemoryStrategy, SearchStrategy,
        VisionStrategy, UnknownStrategy,
    ])
    def test_config_has_extractors(self, strategy_cls):
        s = strategy_cls()
        config = s.get_config()
        assert len(config.extractors) >= 1

    @pytest.mark.parametrize("strategy_cls", [
        ConversationStrategy, CodingStrategy, TerminalStrategy,
        DesktopStrategy, BrowserStrategy, WorkflowStrategy,
        PlanningStrategy, MemoryStrategy, SearchStrategy,
        VisionStrategy, UnknownStrategy,
    ])
    def test_token_budget_positive(self, strategy_cls):
        s = strategy_cls()
        config = s.get_config()
        assert config.token_budget.total > 0
        assert config.token_budget.system > 0
        assert config.token_budget.reserved > 0

    @pytest.mark.parametrize("strategy_cls,intent,expected_total", [
        (ConversationStrategy, IntentType.CONVERSATION, 4096),
        (CodingStrategy, IntentType.CODING, 8192),
        (TerminalStrategy, IntentType.TERMINAL, 4096),
        (DesktopStrategy, IntentType.DESKTOP, 4096),
        (BrowserStrategy, IntentType.BROWSER, 4096),
        (WorkflowStrategy, IntentType.WORKFLOW, 8192),
        (PlanningStrategy, IntentType.PLANNING, 8192),
        (MemoryStrategy, IntentType.MEMORY, 8192),
        (SearchStrategy, IntentType.SEARCH, 4096),
        (VisionStrategy, IntentType.VISION, 8192),
        (UnknownStrategy, IntentType.UNKNOWN, 2048),
    ])
    def test_token_budget_total(self, strategy_cls, intent, expected_total):
        s = strategy_cls()
        assert s.get_config().token_budget.total == expected_total

    @pytest.mark.parametrize("strategy_cls", [
        ConversationStrategy, CodingStrategy, TerminalStrategy,
        DesktopStrategy, BrowserStrategy, WorkflowStrategy,
        PlanningStrategy, MemoryStrategy, SearchStrategy,
        VisionStrategy, UnknownStrategy,
    ])
    def test_retrieval_priority_sources(self, strategy_cls):
        s = strategy_cls()
        config = s.get_config()
        assert len(config.retrieval_priority.sources) >= 1
        for src in config.retrieval_priority.sources:
            assert isinstance(src, str)

    @pytest.mark.parametrize("strategy_cls", [
        ConversationStrategy, CodingStrategy, TerminalStrategy,
        DesktopStrategy, BrowserStrategy, WorkflowStrategy,
        PlanningStrategy, MemoryStrategy, SearchStrategy,
        VisionStrategy, UnknownStrategy,
    ])
    def test_compression_policy_valid(self, strategy_cls):
        s = strategy_cls()
        c = s.get_config().compression_policy
        assert c.strategy in ("summarize", "truncate", "key_point_extraction", "none")
        assert c.max_tokens > 0
        assert 0.0 < c.threshold <= 1.0

    @pytest.mark.parametrize("strategy_cls", [
        ConversationStrategy, CodingStrategy, TerminalStrategy,
        DesktopStrategy, BrowserStrategy, WorkflowStrategy,
        PlanningStrategy, MemoryStrategy, SearchStrategy,
        VisionStrategy, UnknownStrategy,
    ])
    def test_cache_policy_valid(self, strategy_cls):
        s = strategy_cls()
        c = s.get_config().cache_policy
        assert c.ttl_seconds > 0
        assert c.max_entries > 0
        assert c.invalidation in ("lru", "ttl_only", "never")


# ----------------------------------------------------------------
# Unit Tests: StrategyManager
# ----------------------------------------------------------------

class TestStrategyManagerUnit:
    def make_manager(self):
        return StrategyManager()

    def test_init_has_all_11_strategies(self):
        m = self.make_manager()
        assert len(m._strategies) == 11
        for it in IntentType:
            assert it in m._strategies

    def test_get_strategy_returns_correct_type(self):
        m = self.make_manager()
        s = m.get_strategy(IntentType.CODING)
        assert isinstance(s, CodingStrategy)

        s = m.get_strategy(IntentType.CONVERSATION)
        assert isinstance(s, ConversationStrategy)

        s = m.get_strategy(IntentType.UNKNOWN)
        assert isinstance(s, UnknownStrategy)

    def test_get_strategy_fallback_to_unknown(self):
        m = self.make_manager()
        # IntentType enum has 11 members, all covered — test with strategy config
        s = m.get_strategy(IntentType.UNKNOWN)
        assert s.intent_type == IntentType.UNKNOWN

    def test_get_strategy_is_idempotent(self):
        m = self.make_manager()
        s1 = m.get_strategy(IntentType.CODING)
        s2 = m.get_strategy(IntentType.CODING)
        assert s1 is s2

    def test_list_strategies_has_all_intents(self):
        m = self.make_manager()
        listing = m.list_strategies()
        assert len(listing) == 11
        for it in IntentType:
            assert it in listing
            assert listing[it].endswith("Strategy")

    def test_lifecycle_start_shutdown(self):
        m = self.make_manager()
        import anyio
        anyio.run(m.start)
        assert m._running is True
        anyio.run(m.shutdown)
        assert m._running is False

    def test_health_check(self):
        m = self.make_manager()
        h = m.health()
        assert h["status"] == "HEALTHY"
        assert h["details"]["strategy_count"] == 11
        assert h["details"]["last_resolved"] is None

    def test_no_event_bus_does_not_crash(self):
        m = self.make_manager()
        assert m._event_bus is None
        s = m.get_strategy(IntentType.CODING)
        assert s is not None

    def test_unknown_strategy_has_lowest_token_budget(self):
        m = self.make_manager()
        unknown = m.get_strategy(IntentType.UNKNOWN)
        coding = m.get_strategy(IntentType.CODING)
        assert unknown.get_config().token_budget.total < coding.get_config().token_budget.total


# ----------------------------------------------------------------
# Integration Tests: EventBus publication
# ----------------------------------------------------------------

class TestStrategyManagerEventBusIntegration:
    @pytest.mark.anyio
    async def test_subscribes_to_intent_analyzed(self):
        bus = EventBus()
        m = StrategyManager(event_bus=bus)
        await m.start()

        # StrategyResolved events should be published when IntentAnalyzed fires
        resolved_events = []
        bus.subscribe("StrategyResolved", lambda e: resolved_events.append(e))

        await bus.publish(IntentAnalyzed(
            request="write a python function",
            intent=IntentType.CODING,
            confidence=0.9,
            reasoning="coding patterns matched",
        ))

        assert len(resolved_events) == 1
        event = resolved_events[0]
        assert isinstance(event, StrategyResolved)
        assert event.topic == "StrategyResolved"
        assert event.data["intent"] == "coding"
        assert event.data["strategy_name"] == "CodingStrategy"
        assert event.data["token_budget"] == 8192

        await m.shutdown()

    @pytest.mark.anyio
    async def test_resolves_correct_strategy_per_intent(self):
        bus = EventBus()
        m = StrategyManager(event_bus=bus)
        await m.start()

        resolved = []
        bus.subscribe("StrategyResolved", lambda e: resolved.append(e))

        test_cases = [
            ("hello there", "conversation", 4096),
            ("run ls in terminal", "terminal", 4096),
            ("search for something", "search", 4096),
            ("random gibberish", "unknown", 2048),
        ]

        for request, expected_intent, expected_budget in test_cases:
            resolved.clear()
            await bus.publish(IntentAnalyzed(
                request=request,
                intent=IntentType(expected_intent),
                confidence=0.8,
                reasoning="test",
            ))
            assert len(resolved) == 1, f"Failed for '{request}'"
            assert resolved[0].data["intent"] == expected_intent
            assert resolved[0].data["token_budget"] == expected_budget

        await m.shutdown()

    @pytest.mark.anyio
    async def test_updates_last_resolved(self):
        bus = EventBus()
        m = StrategyManager(event_bus=bus)
        await m.start()

        assert m._last_resolved is None

        await bus.publish(IntentAnalyzed(
            request="plan the roadmap",
            intent=IntentType.PLANNING,
            confidence=0.85,
            reasoning="planning patterns matched",
        ))

        assert m._last_resolved == IntentType.PLANNING
        await m.shutdown()

    @pytest.mark.anyio
    async def test_no_event_published_when_not_running(self):
        bus = EventBus()
        m = StrategyManager(event_bus=bus)
        # Not started

        resolved = []
        bus.subscribe("StrategyResolved", lambda e: resolved.append(e))

        await bus.publish(IntentAnalyzed(
            request="hello",
            intent=IntentType.CONVERSATION,
            confidence=1.0,
            reasoning="test",
        ))

        assert len(resolved) == 0

    @pytest.mark.anyio
    async def test_unknown_intent_string_falls_back_to_unknown(self):
        bus = EventBus()
        m = StrategyManager(event_bus=bus)
        await m.start()

        resolved = []
        bus.subscribe("StrategyResolved", lambda e: resolved.append(e))

        await bus.publish(IntentAnalyzed(
            request="xyz",
            intent=IntentType.UNKNOWN,
            confidence=0.5,
            reasoning="no match",
        ))

        assert len(resolved) == 1
        assert resolved[0].data["intent"] == "unknown"
        assert resolved[0].data["strategy_name"] == "UnknownStrategy"

        await m.shutdown()


# ----------------------------------------------------------------
# Regression Tests: Kernel registration and lifecycle
# ----------------------------------------------------------------

class TestStrategyManagerKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_strategy_manager(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("strategy_manager")
            assert svc is not None
            assert isinstance(svc, StrategyManager)

            h = kernel.health()
            assert h.strategy_manager.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_lifecycle_via_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            mgr = kernel.get_service("strategy_manager")
            assert mgr._running is True

            mgr_from_registry = kernel.module_registry.get_module("strategy_manager")
            assert mgr_from_registry is mgr
        finally:
            await kernel.shutdown()

        assert mgr._running is False

    @pytest.mark.anyio
    async def test_strategy_resolved_flow_through_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            event_bus = kernel.get_service("event_bus")

            resolved = []
            event_bus.subscribe("StrategyResolved", lambda e: resolved.append(e))

            # Publish IntentAnalyzed (as the intent analyzer would)
            await event_bus.publish(IntentAnalyzed(
                request="debug this stack trace",
                intent=IntentType.CODING,
                confidence=0.95,
                reasoning="coding patterns matched strongly",
            ))

            assert len(resolved) == 1
            assert resolved[0].data["intent"] == "coding"
            assert resolved[0].data["strategy_name"] == "CodingStrategy"
            assert resolved[0].data["token_budget"] == 8192
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_kernel_boot_shutdown_restart(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()
        svc1 = kernel.get_service("strategy_manager")
        await kernel.shutdown()

        await kernel.boot()
        svc2 = kernel.get_service("strategy_manager")
        assert svc2 is not None
        assert isinstance(svc2, StrategyManager)
        assert svc2 is not svc1
        await kernel.shutdown()

    @pytest.mark.anyio
    async def test_get_strategy_works_after_kernel_boot(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            mgr = kernel.get_service("strategy_manager")
            s = mgr.get_strategy(IntentType.VISION)
            assert s.intent_type == IntentType.VISION
            config = s.get_config()
            assert config.token_budget.total == 8192
            assert "image_analysis_extractor" in config.extractors
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_all_strategies_accessible_after_boot(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            mgr = kernel.get_service("strategy_manager")
            listing = mgr.list_strategies()
            assert len(listing) == 11
            for intent_type, name in listing.items():
                s = mgr.get_strategy(intent_type)
                assert s.__class__.__name__ == name
        finally:
            await kernel.shutdown()
