import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.intent.types import IntentType
from app.tools.base import (
    ToolDefinition, ToolCategory, PermissionLevel, ToolHealth, ToolDependency,
)
from app.tools.registry import ToolRegistry as UniversalToolRegistry
from app.friday.tool_registry import ToolRegistry as LegacyToolRegistry
from app.tools.base_tool import BaseTool
from app.tool_selection.base import (
    ToolSelectionResult, SelectedTool, ToolSelectionContext,
)
from app.tool_execution.base import (
    ExecutionMode, ExecutionStatus, ExecutionContext, ExecutedTool,
    ToolExecutionResult, ExecutionReport,
)
from app.tool_execution.events import (
    ToolExecutionStarted, ToolExecutionCompleted,
    ToolExecutionFailed, ToolExecutionCancelled,
)
from app.tool_execution.result import build_report
from app.tool_execution.scheduler import ExecutionScheduler
from app.tool_execution.executor import ToolExecutionEngine, CancellationToken


# ── Mock Tools ────────────────────────────────────────────────────────────

class MockTool(BaseTool):
    def __init__(self, name: str, delay: float = 0.0,
                 fail: bool = False, output: str = "ok") -> None:
        self._name = name
        self._delay = delay
        self._fail = fail
        self._output = output

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool {self._name}"

    async def execute(self, **kwargs) -> str:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._fail:
            raise RuntimeError(f"{self._name} failed")
        return self._output


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def legacy_registry():
    r = LegacyToolRegistry()
    r.register("healthy_tool", MockTool("healthy_tool"))
    r.register("slow_tool", MockTool("slow_tool", delay=0.2))
    r.register("failing_tool", MockTool("failing_tool", fail=True))
    r.register("fast_tool", MockTool("fast_tool", output="fast_result"))
    r.register("dep_tool", MockTool("dep_tool", output="dep_result"))
    return r


@pytest.fixture
def universal_registry():
    r = UniversalToolRegistry()
    for tid in ["healthy_tool", "slow_tool", "failing_tool", "fast_tool", "dep_tool"]:
        r.register(ToolDefinition(
            id=tid, name=tid, description=f"Tool {tid}",
            category=ToolCategory.FILESYSTEM,
            estimated_latency_ms=50.0,
        ))
    return r


@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def engine(legacy_registry, universal_registry, event_bus):
    return ToolExecutionEngine(legacy_registry, universal_registry, event_bus)


def make_selection(tool_ids: list) -> ToolSelectionResult:
    selected = []
    for tid in tool_ids:
        selected.append(SelectedTool(
            tool=ToolDefinition(id=tid, name=tid, description=f"Tool {tid}",
                                category=ToolCategory.FILESYSTEM),
            score=1.0,
            selection_reason="test",
        ))
    return ToolSelectionResult(selected_tools=selected)


# ── Base Model Tests ──────────────────────────────────────────────────────

class TestBaseModels:
    def test_execution_context_defaults(self):
        ctx = ExecutionContext(tool_id="test")
        assert ctx.tool_id == "test"
        assert ctx.args == {}
        assert ctx.timeout == 30.0
        assert ctx.max_retries == 0
        assert ctx.priority == 0

    def test_executed_tool_defaults(self):
        et = ExecutedTool(tool_id="test")
        assert et.status == ExecutionStatus.PENDING
        assert et.success is False
        assert et.error is None
        assert et.duration_ms == 0.0
        assert et.runtime_ms == 0.0

    def test_executed_tool_success(self):
        et = ExecutedTool(tool_id="test", status=ExecutionStatus.COMPLETED)
        assert et.success is True
        assert et.runtime_ms == 0.0

    def test_execution_result_properties(self):
        r = ToolExecutionResult(execution_id="e1")
        assert r.all_succeeded is True
        assert r.tool_ids == []
        r.results = [ExecutedTool(tool_id="a", status=ExecutionStatus.COMPLETED)]
        assert r.all_succeeded is True
        r.results.append(ExecutedTool(tool_id="b", status=ExecutionStatus.FAILED))
        assert r.all_succeeded is False

    def test_execution_report_defaults(self):
        r = ExecutionReport()
        assert r.total_tools == 0
        assert r.completed == 0
        assert r.errors == []

    def test_execution_mode_values(self):
        assert ExecutionMode.SEQUENTIAL.value == "sequential"
        assert ExecutionMode.PARALLEL.value == "parallel"
        assert ExecutionMode.DEPENDENCY_AWARE.value == "dependency_aware"


# ── Result Builder Tests ──────────────────────────────────────────────────

class TestResultBuilder:
    def test_empty_results(self):
        report = build_report([])
        assert report.total_tools == 0
        assert report.total_duration_ms == 0.0

    def test_all_successful(self):
        now = datetime.now(timezone.utc)
        results = [
            ExecutedTool(tool_id="a", status=ExecutionStatus.COMPLETED,
                         duration_ms=10.0, started_at=now, completed_at=now),
            ExecutedTool(tool_id="b", status=ExecutionStatus.COMPLETED,
                         duration_ms=20.0, started_at=now, completed_at=now),
        ]
        report = build_report(results)
        assert report.total_tools == 2
        assert report.completed == 2

    def test_with_failures(self):
        results = [
            ExecutedTool(tool_id="a", status=ExecutionStatus.COMPLETED),
            ExecutedTool(tool_id="b", status=ExecutionStatus.FAILED,
                         error="oh no"),
        ]
        report = build_report(results)
        assert report.failed == 1
        assert len(report.errors) == 1


# ── Scheduler Tests ───────────────────────────────────────────────────────

class TestExecutionScheduler:
    def test_sequential(self):
        contexts = [ExecutionContext(tool_id="a"), ExecutionContext(tool_id="b")]
        layers = ExecutionScheduler.order_tools(contexts, ExecutionMode.SEQUENTIAL, {})
        assert len(layers) == 2
        assert len(layers[0]) == 1
        assert layers[0][0].tool_id == "a"

    def test_parallel(self):
        contexts = [ExecutionContext(tool_id="a"), ExecutionContext(tool_id="b")]
        layers = ExecutionScheduler.order_tools(contexts, ExecutionMode.PARALLEL, {})
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_dependency_aware_simple(self):
        contexts = [
            ExecutionContext(tool_id="a"),
            ExecutionContext(tool_id="b", priority=1),
        ]
        deps = {"b": ["a"]}
        layers = ExecutionScheduler.order_tools(contexts, ExecutionMode.DEPENDENCY_AWARE, deps)
        assert len(layers) == 2
        assert layers[0][0].tool_id == "a"
        assert layers[1][0].tool_id == "b"

    def test_dependency_aware_no_deps(self):
        contexts = [
            ExecutionContext(tool_id="a"),
            ExecutionContext(tool_id="b"),
        ]
        layers = ExecutionScheduler.order_tools(contexts, ExecutionMode.DEPENDENCY_AWARE, {})
        assert len(layers) == 1
        assert len(layers[0]) == 2


# ── Engine Tests ─────────────────────────────────────────────────────────

class TestToolExecutionEngine:
    @pytest.mark.anyio
    async def test_execute_single_tool(self, engine):
        selection = make_selection(["healthy_tool"])
        result = await engine.execute(selection)
        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.results) == 1
        assert result.results[0].status == ExecutionStatus.COMPLETED
        assert result.results[0].output == "ok"

    @pytest.mark.anyio
    async def test_execute_multiple_sequential(self, engine):
        selection = make_selection(["healthy_tool", "fast_tool"])
        result = await engine.execute(selection, mode=ExecutionMode.SEQUENTIAL)
        assert len(result.results) == 2
        assert all(r.status == ExecutionStatus.COMPLETED for r in result.results)

    @pytest.mark.anyio
    async def test_execute_parallel(self, engine):
        selection = make_selection(["fast_tool", "healthy_tool"])
        result = await engine.execute(selection, mode=ExecutionMode.PARALLEL)
        assert len(result.results) == 2
        assert all(r.status == ExecutionStatus.COMPLETED for r in result.results)

    @pytest.mark.anyio
    async def test_tool_not_found(self, engine):
        selection = make_selection(["nonexistent_tool"])
        result = await engine.execute(selection)
        assert result.results[0].status == ExecutionStatus.FAILED
        assert "not found" in result.results[0].error

    @pytest.mark.anyio
    async def test_tool_not_in_universal_registry(self, legacy_registry):
        r = LegacyToolRegistry()
        r.register("orphan", MockTool("orphan"))
        eng = ToolExecutionEngine(r, universal_tool_registry=None)
        selection = make_selection(["orphan"])
        result = await eng.execute(selection)
        assert result.results[0].status == ExecutionStatus.COMPLETED

    @pytest.mark.anyio
    async def test_execution_with_args(self, legacy_registry, universal_registry, event_bus):
        engine = ToolExecutionEngine(legacy_registry, universal_registry, event_bus)
        selection = make_selection(["healthy_tool"])
        result = await engine.execute(selection, args_overrides={
            "healthy_tool": {"key": "value"},
        })
        assert result.results[0].status == ExecutionStatus.COMPLETED

    @pytest.mark.anyio
    async def test_result_contains_report(self, engine):
        selection = make_selection(["healthy_tool", "fast_tool"])
        result = await engine.execute(selection)
        assert result.report.total_tools == 2
        assert result.report.completed == 2


# ── Timeout Tests ────────────────────────────────────────────────────────

class TestTimeout:
    @pytest.mark.anyio
    async def test_tool_timeout(self, legacy_registry, universal_registry, event_bus):
        r = LegacyToolRegistry()
        r.register("too_slow", MockTool("too_slow", delay=5.0))
        universal_registry.register(ToolDefinition(
            id="too_slow", name="too_slow", description="slow",
            category=ToolCategory.FILESYSTEM,
        ))
        eng = ToolExecutionEngine(r, universal_registry, event_bus)
        selection = make_selection(["too_slow"])
        result = await eng.execute(selection, global_timeout=0.1)
        assert result.results[0].status == ExecutionStatus.TIMEOUT
        assert "Timed out" in result.results[0].error

    @pytest.mark.anyio
    async def test_timeout_count_incremented(self, legacy_registry, universal_registry, event_bus):
        r = LegacyToolRegistry()
        r.register("v_slow", MockTool("v_slow", delay=5.0))
        universal_registry.register(ToolDefinition(
            id="v_slow", name="v_slow", description="slow",
            category=ToolCategory.FILESYSTEM,
        ))
        eng = ToolExecutionEngine(r, universal_registry, event_bus)
        selection = make_selection(["v_slow"])
        await eng.execute(selection, global_timeout=0.1)
        h = eng.health()
        assert h["timeout_count"] > 0


# ── Cancellation Tests ──────────────────────────────────────────────────

class TestCancellation:
    @pytest.mark.anyio
    async def test_cancellation_before_execution(self, engine):
        token = CancellationToken()
        token.cancel()
        selection = make_selection(["healthy_tool"])
        result = await engine.execute(selection, cancellation_token=token)
        assert result.results[0].status == ExecutionStatus.CANCELLED

    @pytest.mark.anyio
    async def test_cancellation_during_execution(self, legacy_registry, universal_registry, event_bus):
        r = LegacyToolRegistry()
        r.register("slowish", MockTool("slowish", delay=0.5))
        universal_registry.register(ToolDefinition(
            id="slowish", name="slowish", description="slow",
            category=ToolCategory.FILESYSTEM,
        ))
        eng = ToolExecutionEngine(r, universal_registry, event_bus)
        selection = make_selection(["slowish", "healthy_tool"])
        token = CancellationToken()

        async def cancel_later():
            await asyncio.sleep(0.05)
            token.cancel()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(cancel_later())
            result = await eng.execute(selection, cancellation_token=token)

        cancelled = [r for r in result.results if r.status == ExecutionStatus.CANCELLED]
        assert len(cancelled) > 0


# ── Failure & Retry Tests ────────────────────────────────────────────────

class TestFailureAndRetry:
    @pytest.mark.anyio
    async def test_failing_tool(self, engine):
        selection = make_selection(["failing_tool"])
        result = await engine.execute(selection)
        assert result.results[0].status == ExecutionStatus.FAILED
        assert "failed" in result.results[0].error

    @pytest.mark.anyio
    async def test_retry_succeeds(self, legacy_registry, universal_registry, event_bus):
        class FlakyTool(BaseTool):
            def __init__(self):
                self._attempts = 0
                self._name = "flaky_tool"

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return "Flaky tool"

            async def execute(self, **kwargs) -> str:
                self._attempts += 1
                if self._attempts < 3:
                    raise RuntimeError(f"Attempt {self._attempts} failed")
                return "success"

        r = LegacyToolRegistry()
        tt = FlakyTool()
        r.register("flaky_tool", tt)
        universal_registry.register(ToolDefinition(
            id="flaky_tool", name="flaky_tool", description="flaky",
            category=ToolCategory.FILESYSTEM,
        ))
        eng = ToolExecutionEngine(r, universal_registry, event_bus)
        from app.tool_execution.base import ExecutionContext
        ctx = ExecutionContext(tool_id="flaky_tool", max_retries=3, retry_delay=0.01)
        et = await eng._execute_single(ctx, "e1", CancellationToken(), 30.0)
        assert et.status == ExecutionStatus.COMPLETED
        assert et.output == "success"
        assert et.retries == 2

    @pytest.mark.anyio
    async def test_failure_count_incremented(self, engine):
        selection = make_selection(["failing_tool"])
        await engine.execute(selection)
        h = engine.health()
        assert h["failure_count"] > 0


# ── Dependency Ordering Tests ─────────────────────────────────────────────

class TestDependencyOrdering:
    @pytest.mark.anyio
    async def test_dependency_aware_execution(self, engine):
        selection = make_selection(["dep_tool", "healthy_tool"])
        result = await engine.execute(
            selection,
            mode=ExecutionMode.DEPENDENCY_AWARE,
            dependency_map={"healthy_tool": ["dep_tool"]},
        )
        assert len(result.results) == 2
        dep_result = next(r for r in result.results if r.tool_id == "dep_tool")
        main_result = next(r for r in result.results if r.tool_id == "healthy_tool")
        assert dep_result.status == ExecutionStatus.COMPLETED
        assert main_result.status == ExecutionStatus.COMPLETED

    def test_scheduler_topological(self):
        contexts = [
            ExecutionContext(tool_id="a"),
            ExecutionContext(tool_id="b"),
            ExecutionContext(tool_id="c"),
        ]
        deps = {"c": ["a", "b"]}
        layers = ExecutionScheduler.order_tools(contexts, ExecutionMode.DEPENDENCY_AWARE, deps)
        assert len(layers) >= 2
        layer0_ids = {c.tool_id for c in layers[0]}
        assert "c" not in layer0_ids


# ── Event Tests ───────────────────────────────────────────────────────────

class TestExecutionEvents:
    @pytest.mark.anyio
    async def test_publishes_started_and_completed(self, engine, event_bus):
        selection = make_selection(["healthy_tool"])
        await engine.execute(selection)
        started = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], ToolExecutionStarted)
        ]
        completed = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], ToolExecutionCompleted)
        ]
        assert len(started) > 0
        assert len(completed) > 0

    @pytest.mark.anyio
    async def test_publishes_failed_event(self, engine, event_bus):
        selection = make_selection(["failing_tool"])
        await engine.execute(selection)
        failed = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], ToolExecutionFailed)
        ]
        assert len(failed) > 0

    @pytest.mark.anyio
    async def test_publishes_cancelled_event(self, engine, event_bus):
        token = CancellationToken()
        token.cancel()
        selection = make_selection(["healthy_tool"])
        await engine.execute(selection, cancellation_token=token)
        cancelled = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], ToolExecutionCancelled)
        ]
        assert len(cancelled) > 0

    @pytest.mark.anyio
    async def test_no_event_bus_does_not_crash(self, legacy_registry, universal_registry):
        eng = ToolExecutionEngine(legacy_registry, universal_registry, event_bus=None)
        selection = make_selection(["healthy_tool"])
        result = await eng.execute(selection)
        assert result.results[0].status == ExecutionStatus.COMPLETED


# ── Health Tests ──────────────────────────────────────────────────────────

class TestExecutionHealth:
    def test_health_defaults(self, engine):
        h = engine.health()
        assert h["status"] == "healthy"
        assert h["execution_count"] == 0
        assert h["failure_count"] == 0

    @pytest.mark.anyio
    async def test_health_after_execution(self, engine):
        selection = make_selection(["healthy_tool"])
        await engine.execute(selection)
        h = engine.health()
        assert h["execution_count"] == 1
        assert h["average_latency_ms"] >= 0

    @pytest.mark.anyio
    async def test_health_tracks_failures(self, engine):
        selection = make_selection(["failing_tool"])
        await engine.execute(selection)
        h = engine.health()
        assert h["failure_count"] >= 1


# ── Build Context Tests ──────────────────────────────────────────────────

class TestBuildContexts:
    def test_build_contexts_from_selection(self, engine):
        selection = make_selection(["healthy_tool", "fast_tool"])
        contexts = engine._build_contexts(selection, {})
        assert len(contexts) == 2
        assert contexts[0].tool_id == "healthy_tool"
        assert contexts[1].tool_id == "fast_tool"

    def test_build_contexts_with_args(self, engine):
        selection = make_selection(["healthy_tool"])
        contexts = engine._build_contexts(selection, {
            "healthy_tool": {"key": "value"},
        })
        assert contexts[0].args == {"key": "value"}
