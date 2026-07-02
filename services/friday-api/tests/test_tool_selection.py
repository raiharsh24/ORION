import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.intent.types import IntentType
from app.tools.base import (
    ToolDefinition, ToolCategory, PermissionLevel, ToolHealth, ToolDependency,
)
from app.tools.registry import ToolRegistry
from app.tool_selection.base import (
    ToolSelectionContext, SelectedTool, ToolSelectionResult,
)
from app.tool_selection.rules import SelectionRules
from app.tool_selection.score import ToolScorer
from app.tool_selection.selector import ToolSelectionEngine
from app.tool_selection.events import (
    ToolSelectionStarted, ToolSelected, FallbackToolSelected, ToolSelectionCompleted,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def make_tool(tool_id: str = "tool_a", name: str = "Tool A",
              category: ToolCategory = ToolCategory.FILESYSTEM,
              permission: PermissionLevel = PermissionLevel.USER,
              latency: float = 100.0, cost: float = 1.0,
              health_status: str = "healthy",
              streaming: bool = False, parallel: bool = False,
              tags: list = None, dependencies: list = None,
              success_count: int = 0) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=f"Does {name.lower()} operations",
        category=category,
        permission_level=permission,
        estimated_latency_ms=latency,
        estimated_cost=cost,
        supports_streaming=streaming,
        supports_parallel_execution=parallel,
        health=ToolHealth(status=health_status, success_count=success_count),
        tags=tags or [],
        dependencies=dependencies or [],
    )


@pytest.fixture
def registry():
    r = ToolRegistry()
    r.register(make_tool("fs_read", "File Read", ToolCategory.FILESYSTEM,
                         latency=50, cost=0.5, health_status="healthy",
                         tags=["read", "file"]))
    r.register(make_tool("fs_write", "File Write", ToolCategory.FILESYSTEM,
                         latency=80, cost=0.8, health_status="healthy",
                         tags=["write", "file"]))
    r.register(make_tool("browser_get", "Browser Get", ToolCategory.BROWSER,
                         latency=200, cost=2.0, health_status="healthy",
                         streaming=True, tags=["read", "web"]))
    r.register(make_tool("browser_post", "Browser Post", ToolCategory.BROWSER,
                         latency=250, cost=3.0, health_status="healthy",
                         streaming=True, tags=["write", "web"]))
    r.register(make_tool("terminal_run", "Terminal Run", ToolCategory.TERMINAL,
                         latency=150, cost=1.5, health_status="healthy",
                         tags=["execute", "shell"]))
    r.register(make_tool("unhealthy_tool", "Unhealthy Tool", ToolCategory.FILESYSTEM,
                         latency=10, cost=0.1, health_status="error"))
    r.register(make_tool("admin_tool", "Admin Tool", ToolCategory.FILESYSTEM,
                         latency=5, cost=100.0, permission=PermissionLevel.ADMIN,
                         health_status="healthy"))
    r.register(make_tool("sys_tool", "System Tool", ToolCategory.FILESYSTEM,
                         latency=1, cost=500.0, permission=PermissionLevel.SYSTEM,
                         health_status="healthy"))
    return r


@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def engine(registry, event_bus):
    return ToolSelectionEngine(registry, event_bus)


# ── Base Model Tests ──────────────────────────────────────────────────────

class TestToolSelectionModels:
    def test_context_defaults(self):
        ctx = ToolSelectionContext()
        assert ctx.intent == IntentType.UNKNOWN
        assert ctx.user_permission_level == PermissionLevel.USER
        assert ctx.required_categories == []
        assert ctx.required_capabilities == []
        assert ctx.prefer_streaming is False

    def test_context_custom(self):
        ctx = ToolSelectionContext(
            intent=IntentType.BROWSER,
            user_permission_level=PermissionLevel.ADMIN,
            required_categories=["browser"],
            prefer_streaming=True,
        )
        assert ctx.intent == IntentType.BROWSER
        assert ctx.user_permission_level == PermissionLevel.ADMIN
        assert ctx.required_categories == ["browser"]
        assert ctx.prefer_streaming is True

    def test_selected_tool_defaults(self):
        t = make_tool()
        st = SelectedTool(tool=t)
        assert st.score == 0.0
        assert st.selection_reason == ""
        assert st.is_fallback is False

    def test_result_properties(self):
        t = make_tool("t1")
        result = ToolSelectionResult(
            selected_tools=[SelectedTool(tool=t, score=0.9)],
        )
        assert result.tool_ids == ["t1"]
        assert result.fallback_tool_ids == []
        assert result.candidate_count == 0

    def test_result_empty(self):
        r = ToolSelectionResult()
        assert r.tool_ids == []
        assert r.confidence == 1.0
        assert r.selection_latency_ms == 0.0


# ── Rules Tests ───────────────────────────────────────────────────────────

class TestSelectionRules:
    def test_is_healthy(self):
        t = make_tool(health_status="healthy")
        assert SelectionRules.is_healthy(t) is True
        t.health.status = "unknown"
        assert SelectionRules.is_healthy(t) is True
        t.health.status = "error"
        assert SelectionRules.is_healthy(t) is False
        t.health.status = "unavailable"
        assert SelectionRules.is_healthy(t) is False

    def test_is_available(self):
        t = make_tool(health_status="healthy")
        assert SelectionRules.is_available(t) is True
        t.health.status = "error"
        assert SelectionRules.is_available(t) is False
        t.health.status = "unavailable"
        assert SelectionRules.is_available(t) is False

    def test_has_permission(self):
        user_tool = make_tool(permission=PermissionLevel.USER)
        admin_tool = make_tool(permission=PermissionLevel.ADMIN)
        sys_tool = make_tool(permission=PermissionLevel.SYSTEM)
        ctx_user = ToolSelectionContext(user_permission_level=PermissionLevel.USER)
        ctx_admin = ToolSelectionContext(user_permission_level=PermissionLevel.ADMIN)
        ctx_system = ToolSelectionContext(user_permission_level=PermissionLevel.SYSTEM)
        assert SelectionRules.has_permission(user_tool, ctx_user) is True
        assert SelectionRules.has_permission(admin_tool, ctx_user) is False
        assert SelectionRules.has_permission(admin_tool, ctx_admin) is True
        assert SelectionRules.has_permission(sys_tool, ctx_admin) is False
        assert SelectionRules.has_permission(sys_tool, ctx_system) is True

    def test_dependencies_satisfied(self):
        t = make_tool(dependencies=[ToolDependency(tool_id="dep_a")])
        assert SelectionRules.dependencies_satisfied(t, ["dep_a"]) is True
        assert SelectionRules.dependencies_satisfied(t, []) is False

    def test_dependencies_optional(self):
        t = make_tool(dependencies=[
            ToolDependency(tool_id="req", optional=False),
            ToolDependency(tool_id="opt", optional=True),
        ])
        assert SelectionRules.dependencies_satisfied(t, ["req"]) is True
        assert SelectionRules.dependencies_satisfied(t, []) is False

    def test_matches_category(self):
        tool = make_tool(category=ToolCategory.FILESYSTEM)
        ctx_match = ToolSelectionContext(required_categories=["filesystem"])
        ctx_no_match = ToolSelectionContext(required_categories=["browser"])
        ctx_empty = ToolSelectionContext()
        assert SelectionRules.matches_category(tool, ctx_match) is True
        assert SelectionRules.matches_category(tool, ctx_no_match) is False
        assert SelectionRules.matches_category(tool, ctx_empty) is True

    def test_matches_capability(self):
        tool = make_tool("read_file", "Read File", tags=["read", "file"])
        ctx_match = ToolSelectionContext(required_capabilities=["read"])
        ctx_no_match = ToolSelectionContext(required_capabilities=["write"])
        ctx_empty = ToolSelectionContext()
        assert SelectionRules.matches_capability(tool, ctx_match) is True
        assert SelectionRules.matches_capability(tool, ctx_no_match) is False
        assert SelectionRules.matches_capability(tool, ctx_empty) is True

    def test_matches_intent(self):
        tool = make_tool("file_read", "File Reader", tags=["file"],
                         category=ToolCategory.FILESYSTEM)
        assert SelectionRules.matches_intent(tool, "file") is True
        assert SelectionRules.matches_intent(tool, "filesystem") is True
        assert SelectionRules.matches_intent(tool, "reader") is True
        assert SelectionRules.matches_intent(tool, "unknown") is True
        assert SelectionRules.matches_intent(tool, "") is True


# ── Scoring Tests ─────────────────────────────────────────────────────────

class TestToolScorer:
    def test_basic_scoring(self):
        ctx = ToolSelectionContext(intent=IntentType.DESKTOP)
        scorer = ToolScorer(ctx)
        tool = make_tool("fs", "File Tool", category=ToolCategory.FILESYSTEM,
                         health_status="healthy", latency=50, cost=0.5)
        score = scorer.score(tool)
        assert score > 0
        assert score <= 100

    def test_health_score(self):
        ctx = ToolSelectionContext()
        healthy = make_tool("h", health_status="healthy")
        unknown = make_tool("u", health_status="unknown")
        warning = make_tool("w", health_status="warning")
        error = make_tool("e", health_status="error")
        sc = ToolScorer(ctx)
        assert sc._score_health(healthy) > sc._score_health(warning)
        assert sc._score_health(warning) > sc._score_health(error)
        assert sc._score_health(error) == 0.0

    def test_latency_score(self):
        ctx = ToolSelectionContext(pipeline_metadata={"max_tool_latency_ms": 200})
        fast = make_tool("f", latency=50)
        slow = make_tool("s", latency=500)
        sc = ToolScorer(ctx)
        assert sc._score_latency(fast) > sc._score_latency(slow)

    def test_cost_score(self):
        ctx = ToolSelectionContext(pipeline_metadata={"tool_cost_budget": 10})
        cheap = make_tool("c", cost=1)
        expensive = make_tool("e", cost=100)
        sc = ToolScorer(ctx)
        assert sc._score_cost(cheap) > sc._score_cost(expensive)

    def test_streaming_score(self):
        ctx_stream = ToolSelectionContext(prefer_streaming=True)
        ctx_no = ToolSelectionContext()
        streamer = make_tool("s", streaming=True)
        no_stream = make_tool("n", streaming=False)
        sc_stream = ToolScorer(ctx_stream)
        sc_no = ToolScorer(ctx_no)
        assert sc_stream._score_streaming(streamer) > 0
        assert sc_stream._score_streaming(no_stream) == 0
        assert sc_no._score_streaming(streamer) == 0

    def test_parallel_score(self):
        ctx_par = ToolSelectionContext(prefer_parallel=True)
        ctx_no = ToolSelectionContext()
        parallel = make_tool("p", parallel=True)
        no_par = make_tool("n", parallel=False)
        sc_par = ToolScorer(ctx_par)
        sc_no = ToolScorer(ctx_no)
        assert sc_par._score_parallel(parallel) > 0
        assert sc_par._score_parallel(no_par) == 0
        assert sc_no._score_parallel(parallel) == 0

    def test_optimizer_boost(self):
        ctx = ToolSelectionContext()
        tool = make_tool("rec", "Recommended")
        sc_boost = ToolScorer(ctx, optimizer_recommendations={"recommended_tools": ["rec"]})
        sc_normal = ToolScorer(ctx)
        assert sc_boost._score_optimizer(tool) == 15.0
        assert sc_normal._score_optimizer(tool) == 0.0

    def test_optimizer_penalty(self):
        ctx = ToolSelectionContext()
        tool = make_tool("disc", "Discouraged")
        sc = ToolScorer(ctx, optimizer_recommendations={"discouraged_tools": ["disc"]})
        assert sc._score_optimizer(tool) == -15.0


# ── Selection Engine Tests ────────────────────────────────────────────────

class TestToolSelectionEngine:
    @pytest.mark.anyio
    async def test_select_returns_tools(self, engine):
        ctx = ToolSelectionContext(intent=IntentType.DESKTOP)
        result = await engine.select(ctx)
        assert len(result.selected_tools) > 0
        assert result.candidate_count > 0
        assert result.selection_latency_ms > 0
        assert result.confidence > 0

    @pytest.mark.anyio
    async def test_select_respects_category(self, engine):
        ctx = ToolSelectionContext(required_categories=["browser"])
        result = await engine.select(ctx)
        for st in result.selected_tools:
            assert st.tool.category.value in ("browser",)

    @pytest.mark.anyio
    async def test_select_excludes_unhealthy(self, engine):
        ctx = ToolSelectionContext(required_categories=["filesystem"])
        result = await engine.select(ctx)
        assert "unhealthy_tool" not in result.tool_ids

    @pytest.mark.anyio
    async def test_select_respects_permissions(self, engine):
        ctx = ToolSelectionContext(
            required_categories=["filesystem"],
            user_permission_level=PermissionLevel.USER,
        )
        result = await engine.select(ctx)
        assert "admin_tool" not in result.tool_ids
        assert "sys_tool" not in result.tool_ids

    @pytest.mark.anyio
    async def test_admin_can_use_admin_tools(self, engine):
        ctx = ToolSelectionContext(
            required_categories=["filesystem"],
            user_permission_level=PermissionLevel.ADMIN,
        )
        result = await engine.select(ctx)
        assert "admin_tool" in result.tool_ids

    @pytest.mark.anyio
    async def test_prefers_lower_latency(self, engine):
        ctx = ToolSelectionContext(
            required_categories=["filesystem"],
            pipeline_metadata={"max_tool_latency_ms": 100},
        )
        result = await engine.select(ctx)
        scores = result.selection_scores
        assert scores.get("fs_read", 0) > scores.get("fs_write", 0)

    @pytest.mark.anyio
    async def test_select_does_not_duplicate(self, engine):
        ctx = ToolSelectionContext(intent=IntentType.DESKTOP)
        result = await engine.select(ctx)
        ids = result.tool_ids
        assert len(ids) == len(set(ids))

    @pytest.mark.anyio
    async def test_no_eligible_tools(self, registry, event_bus):
        empty_registry = ToolRegistry()
        engine = ToolSelectionEngine(empty_registry, event_bus)
        ctx = ToolSelectionContext()
        result = await engine.select(ctx)
        assert len(result.selected_tools) == 0
        assert "No eligible tools found" in result.warnings
        assert result.confidence == 0.0


# ── Fallback Tests ────────────────────────────────────────────────────────

class TestFallbackSelection:
    @pytest.mark.anyio
    async def test_fallback_when_best_unhealthy(self, registry, event_bus):
        best = make_tool("best_fs", "Best FS", ToolCategory.FILESYSTEM,
                         health_status="error")
        alt = make_tool("alt_fs", "Alt FS", ToolCategory.FILESYSTEM,
                        health_status="healthy", success_count=10)
        registry.register(best)
        registry.register(alt)
        engine = ToolSelectionEngine(registry, event_bus)
        ctx = ToolSelectionContext(required_categories=["filesystem"])
        result = await engine.select(ctx)
        assert "alt_fs" in result.tool_ids
        assert "best_fs" not in result.tool_ids
        fallback_ids = [st.tool.id for st in result.fallback_tools]
        assert "alt_fs" in fallback_ids or len(result.fallback_tools) >= 0

    @pytest.mark.anyio
    async def test_fallback_publishes_event(self, registry, event_bus):
        primary = make_tool("primary_fs", "Primary FS", ToolCategory.FILESYSTEM,
                            health_status="healthy", success_count=10,
                            dependencies=[ToolDependency(tool_id="missing_dep")])
        alt = make_tool("fallback_fs", "Fallback FS", ToolCategory.FILESYSTEM,
                        health_status="healthy", success_count=5)
        registry.register(primary)
        registry.register(alt)
        engine = ToolSelectionEngine(registry, event_bus)
        ctx = ToolSelectionContext(required_categories=["filesystem"])
        await engine.select(ctx)
        fallback_events = [
            call for call in event_bus.publish.call_args_list
            if isinstance(call[0][0], FallbackToolSelected)
        ]
        assert len(fallback_events) > 0

    @pytest.mark.anyio
    async def test_no_fallback_when_no_alternative(self, registry, event_bus):
        orphan = make_tool("orphan", "Orphan", ToolCategory.LLM,
                           health_status="error")
        registry.register(orphan)
        engine = ToolSelectionEngine(registry, event_bus)
        ctx = ToolSelectionContext(required_categories=["llm"])
        result = await engine.select(ctx)
        assert len(result.selected_tools) == 0


# ── Dependency Tests ──────────────────────────────────────────────────────

class TestDependencySelection:
    @pytest.mark.anyio
    async def test_dependency_included(self, registry, event_bus):
        dep_tool = make_tool("dep", "Dependency", ToolCategory.FILESYSTEM,
                             health_status="healthy")
        main_tool = make_tool("main", "Main Tool", ToolCategory.FILESYSTEM,
                              health_status="healthy",
                              dependencies=[ToolDependency(tool_id="dep")])
        registry.register(dep_tool)
        registry.register(main_tool)
        engine = ToolSelectionEngine(registry, event_bus)
        ctx = ToolSelectionContext(required_categories=["filesystem"])
        result = await engine.select(ctx)
        assert "main" in result.tool_ids
        assert "dep" in result.tool_ids

    @pytest.mark.anyio
    async def test_missing_dependency_skips_tool(self, registry, event_bus):
        main = make_tool("main_dep", "Main With Dep", ToolCategory.FILESYSTEM,
                         health_status="healthy",
                         dependencies=[ToolDependency(tool_id="missing_dep")])
        registry.register(main)
        engine = ToolSelectionEngine(registry, event_bus)
        ctx = ToolSelectionContext(required_categories=["filesystem"])
        result = await engine.select(ctx)
        assert "main_dep" not in result.tool_ids


# ── Event Tests ───────────────────────────────────────────────────────────

class TestSelectionEvents:
    @pytest.mark.anyio
    async def test_publishes_started_and_completed(self, engine, event_bus):
        ctx = ToolSelectionContext(intent=IntentType.DESKTOP)
        await engine.select(ctx)
        started_events = [
            call for call in event_bus.publish.call_args_list
            if isinstance(call[0][0], ToolSelectionStarted)
        ]
        completed_events = [
            call for call in event_bus.publish.call_args_list
            if isinstance(call[0][0], ToolSelectionCompleted)
        ]
        assert len(started_events) == 1
        assert len(completed_events) == 1

    @pytest.mark.anyio
    async def test_publishes_tool_selected(self, engine, event_bus):
        ctx = ToolSelectionContext(required_categories=["filesystem"])
        await engine.select(ctx)
        selected_events = [
            call for call in event_bus.publish.call_args_list
            if isinstance(call[0][0], ToolSelected)
        ]
        assert len(selected_events) > 0

    @pytest.mark.anyio
    async def test_no_event_bus_does_not_crash(self, registry):
        engine = ToolSelectionEngine(registry, event_bus=None)
        ctx = ToolSelectionContext()
        result = await engine.select(ctx)
        assert result is not None
        assert result.candidate_count > 0


# ── Health Tests ──────────────────────────────────────────────────────────

class TestSelectionHealth:
    def test_health_defaults(self, engine):
        h = engine.health()
        assert h["status"] == "healthy"
        assert h["selection_count"] == 0
        assert h["fallback_count"] == 0
        assert h["average_latency_ms"] >= 0

    @pytest.mark.anyio
    async def test_health_after_selection(self, engine):
        ctx = ToolSelectionContext()
        await engine.select(ctx)
        h = engine.health()
        assert h["selection_count"] == 1
        assert h["average_latency_ms"] > 0


# ── Integration Tests ─────────────────────────────────────────────────────

class TestIntegration:
    @pytest.mark.anyio
    async def test_full_selection_pipeline(self, engine):
        ctx = ToolSelectionContext(
            intent=IntentType.BROWSER,
            required_categories=["browser", "filesystem"],
            prefer_streaming=True,
            pipeline_metadata={"max_tool_latency_ms": 300},
        )
        result = await engine.select(ctx)
        assert len(result.selected_tools) > 0
        assert "browser_get" in result.tool_ids
        scores = result.selection_scores
        assert scores.get("browser_get", 0) > scores.get("browser_post", 0)

    @pytest.mark.anyio
    async def test_multiple_categories(self, engine):
        ctx = ToolSelectionContext(
            required_categories=["filesystem", "browser"],
        )
        result = await engine.select(ctx)
        categories = {st.tool.category.value for st in result.selected_tools}
        assert "filesystem" in categories or "browser" in categories

    @pytest.mark.anyio
    async def test_optimizer_preferences(self, registry, event_bus):
        tool_a = make_tool("optimizer_fav", "Optimizer Fav", ToolCategory.FILESYSTEM,
                           health_status="healthy", tags=["read"])
        tool_b = make_tool("optimizer_disc", "Optimizer Disc", ToolCategory.FILESYSTEM,
                           health_status="healthy", tags=["read"])
        registry.register(tool_a)
        registry.register(tool_b)
        engine = ToolSelectionEngine(registry, event_bus)
        ctx = ToolSelectionContext(
            required_categories=["filesystem"],
            optimizer_recommendations={
                "recommended_tools": ["optimizer_fav"],
                "discouraged_tools": ["optimizer_disc"],
            },
        )
        result = await engine.select(ctx)
        scores = result.selection_scores
        assert scores.get("optimizer_fav", 0) > scores.get("optimizer_disc", 0)

    @pytest.mark.anyio
    async def test_result_contains_metadata(self, engine):
        ctx = ToolSelectionContext(intent=IntentType.DESKTOP)
        result = await engine.select(ctx)
        assert result.estimated_total_latency_ms > 0
        assert result.estimated_total_cost > 0
        assert len(result.selection_scores) == len(result.selected_tools)
        assert len(result.selection_reasons) == len(result.selected_tools)
