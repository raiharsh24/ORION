import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from app.tools.base import ToolDefinition, ToolCategory, ToolHealth
from app.tools.base_tool import BaseTool
from app.friday.tool_registry import ToolRegistry as LegacyToolRegistry
from app.tools.registry import ToolRegistry as UniversalToolRegistry
from app.tool_execution.executor import ToolExecutionEngine, CancellationToken
from app.tool_selection.base import ToolSelectionResult, SelectedTool
from app.workflow_engine.base import (
    WorkflowGraph, WorkflowNode, WorkflowEdge, WorkflowNodeType,
    WorkflowStatus, WorkflowContext, ExecutedNode, WorkflowExecutionResult,
)
from app.workflow_engine.graph import WorkflowGraphBuilder, WorkflowValidator
from app.workflow_engine.planner import WorkflowPlanner
from app.workflow_engine.executor import WorkflowExecutor
from app.workflow_engine.events import (
    WorkflowStarted, WorkflowNodeStarted, WorkflowNodeCompleted,
    WorkflowCompleted, WorkflowFailed, WorkflowCancelled,
)
from app.workflow_engine.result import build_workflow_report


# ── Mock Tool ────────────────────────────────────────────────────────────

class MockWfTool(BaseTool):
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
        return f"Mock {self._name}"

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
    r.register("tool_a", MockWfTool("tool_a", output="a_done"))
    r.register("tool_b", MockWfTool("tool_b", output="b_done"))
    r.register("tool_c", MockWfTool("tool_c", output="c_done"))
    r.register("tool_d", MockWfTool("tool_d", output="d_done"))
    r.register("failing", MockWfTool("failing", fail=True))
    r.register("slow", MockWfTool("slow", delay=0.3, output="slow_done"))
    return r


@pytest.fixture
def universal_registry():
    r = UniversalToolRegistry()
    for tid in ["tool_a", "tool_b", "tool_c", "tool_d", "failing", "slow"]:
        r.register(ToolDefinition(
            id=tid, name=tid, description=f"Tool {tid}",
            category=ToolCategory.FILESYSTEM,
        ))
    return r


@pytest.fixture
def tool_engine(legacy_registry, universal_registry):
    return ToolExecutionEngine(legacy_registry, universal_registry, event_bus=None)


@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def workflow_engine(tool_engine, event_bus):
    return WorkflowExecutor(tool_engine, event_bus)


# ── Base Model Tests ──────────────────────────────────────────────────────

class TestBaseModels:
    def test_workflow_node_defaults(self):
        n = WorkflowNode(id="n1")
        assert n.id == "n1"
        assert n.node_type == WorkflowNodeType.TOOL
        assert n.tool_id == ""
        assert n.timeout == 60.0
        assert n.max_retries == 0

    def test_workflow_edge(self):
        e = WorkflowEdge(source_id="a", target_id="b")
        assert e.source_id == "a"
        assert e.target_id == "b"

    def test_workflow_graph_add_node(self):
        g = WorkflowGraph()
        g.add_node(WorkflowNode(id="n1"))
        assert g.node_count == 1
        assert "n1" in g.nodes

    def test_workflow_graph_add_edge(self):
        g = WorkflowGraph()
        g.add_node(WorkflowNode(id="a"))
        g.add_node(WorkflowNode(id="b"))
        g.add_edge("a", "b")
        assert g.edge_count == 1
        assert g.get_children("a") == ["b"]
        assert g.get_parents("b") == ["a"]

    def test_executed_node_defaults(self):
        en = ExecutedNode(node_id="n1")
        assert en.node_id == "n1"
        assert en.status == WorkflowStatus.PENDING
        assert en.success is False

    def test_executed_node_success(self):
        en = ExecutedNode(node_id="n1", status=WorkflowStatus.COMPLETED)
        assert en.success is True

    def test_workflow_status_values(self):
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"
        assert WorkflowStatus.SKIPPED.value == "skipped"


# ── Graph Tests ──────────────────────────────────────────────────────────

class TestWorkflowGraphBuilder:
    def test_build_empty(self):
        g = WorkflowGraphBuilder.build([], [])
        assert g.node_count == 0
        assert g.entry_node_ids == []

    def test_build_single_node(self):
        n = WorkflowNode(id="a")
        g = WorkflowGraphBuilder.build([n], [])
        assert g.node_count == 1
        assert g.entry_node_ids == ["a"]

    def test_topological_sort_linear(self):
        nodes = [
            WorkflowNode(id="a"),
            WorkflowNode(id="b"),
            WorkflowNode(id="c"),
        ]
        edges = [
            WorkflowEdge("a", "b"),
            WorkflowEdge("b", "c"),
        ]
        g = WorkflowGraphBuilder.build(nodes, edges)
        layers = WorkflowGraphBuilder.topological_sort(g)
        assert len(layers) == 3
        assert layers[0] == ["a"]
        assert layers[1] == ["b"]
        assert layers[2] == ["c"]

    def test_topological_sort_diamond(self):
        nodes = [
            WorkflowNode(id="start"),
            WorkflowNode(id="left"),
            WorkflowNode(id="right"),
            WorkflowNode(id="end"),
        ]
        edges = [
            WorkflowEdge("start", "left"),
            WorkflowEdge("start", "right"),
            WorkflowEdge("left", "end"),
            WorkflowEdge("right", "end"),
        ]
        g = WorkflowGraphBuilder.build(nodes, edges)
        layers = WorkflowGraphBuilder.topological_sort(g)
        assert layers[0] == ["start"]
        assert set(layers[1]) == {"left", "right"}
        assert layers[2] == ["end"]


class TestWorkflowValidator:
    def test_validate_valid(self):
        nodes = [WorkflowNode(id="a", tool_id="tool_a")]
        g = WorkflowGraphBuilder.build(nodes, [])
        errors = WorkflowValidator.validate(g)
        assert errors == []

    def test_validate_tool_node_missing_tool_id(self):
        nodes = [WorkflowNode(id="a", node_type=WorkflowNodeType.TOOL, tool_id="")]
        g = WorkflowGraphBuilder.build(nodes, [])
        errors = WorkflowValidator.validate(g)
        assert len(errors) > 0
        assert "no tool_id" in errors[0]

    def test_validate_cycle(self):
        nodes = [
            WorkflowNode(id="a", tool_id="tool_a"),
            WorkflowNode(id="b", tool_id="tool_b"),
        ]
        edges = [
            WorkflowEdge("a", "b"),
            WorkflowEdge("b", "a"),
        ]
        g = WorkflowGraphBuilder.build(nodes, edges)
        errors = WorkflowValidator.validate(g)
        assert len(errors) > 0
        assert any("Cycle" in e for e in errors)


# ── Planner Tests ─────────────────────────────────────────────────────────

class TestWorkflowPlanner:
    def test_plan_from_selection(self):
        selection = ToolSelectionResult(selected_tools=[
            SelectedTool(
                tool=ToolDefinition(id="ta", name="Tool A", description="",
                                    category=ToolCategory.FILESYSTEM),
                score=1.0,
            ),
            SelectedTool(
                tool=ToolDefinition(id="tb", name="Tool B", description="",
                                    category=ToolCategory.FILESYSTEM),
                score=0.9,
            ),
        ])
        graph = WorkflowPlanner.plan_from_selection(selection)
        assert graph.node_count == 2
        assert "ta" in graph.nodes
        assert "tb" in graph.nodes
        assert graph.nodes["ta"].tool_id == "ta"
        assert graph.nodes["ta"].name == "Tool A"

    def test_plan_with_edges(self):
        selection = ToolSelectionResult(selected_tools=[
            SelectedTool(
                tool=ToolDefinition(id="ta", name="Tool A", description="",
                                    category=ToolCategory.FILESYSTEM),
                score=1.0,
            ),
            SelectedTool(
                tool=ToolDefinition(id="tb", name="Tool B", description="",
                                    category=ToolCategory.FILESYSTEM),
                score=0.9,
            ),
        ])
        edges = [WorkflowEdge("ta", "tb")]
        graph = WorkflowPlanner.plan_from_selection(selection, edges=edges)
        assert graph.edge_count == 1
        assert graph.get_children("ta") == ["tb"]


# ── Result Builder Tests ──────────────────────────────────────────────────

class TestResultBuilder:
    def test_empty(self):
        result = build_workflow_report({}, WorkflowContext(execution_id="e1"), 0.0)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.total_duration_ms == 0.0

    def test_all_completed(self):
        now = datetime.now(timezone.utc)
        node_results = {
            "a": ExecutedNode(node_id="a", status=WorkflowStatus.COMPLETED,
                              duration_ms=10.0, started_at=now, completed_at=now),
            "b": ExecutedNode(node_id="b", status=WorkflowStatus.COMPLETED,
                              duration_ms=20.0, started_at=now, completed_at=now),
        }
        result = build_workflow_report(node_results, WorkflowContext(execution_id="e1"), 30.0)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.total_duration_ms == 30.0

    def test_failed_node(self):
        node_results = {
            "a": ExecutedNode(node_id="a", status=WorkflowStatus.FAILED,
                              error="something broke"),
        }
        result = build_workflow_report(node_results, WorkflowContext(execution_id="e1"), 5.0)
        assert result.status == WorkflowStatus.FAILED
        assert result.failed_node_id == "a"
        assert len(result.errors) > 0


# ── Workflow Execution Tests ─────────────────────────────────────────────

class TestWorkflowExecution:
    @pytest.mark.anyio
    async def test_execute_single_node(self, workflow_engine):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.node_results["a"].status == WorkflowStatus.COMPLETED
        assert result.node_results["a"].output == "a_done"

    @pytest.mark.anyio
    async def test_execute_linear_workflow(self, workflow_engine):
        nodes = [
            WorkflowNode(id="a", tool_id="tool_a"),
            WorkflowNode(id="b", tool_id="tool_b"),
            WorkflowNode(id="c", tool_id="tool_c"),
        ]
        edges = [
            WorkflowEdge("a", "b"),
            WorkflowEdge("b", "c"),
        ]
        graph = WorkflowGraphBuilder.build(nodes, edges)
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.COMPLETED
        for nid in ["a", "b", "c"]:
            assert result.node_results[nid].status == WorkflowStatus.COMPLETED

    @pytest.mark.anyio
    async def test_execute_parallel_branches(self, workflow_engine):
        nodes = [
            WorkflowNode(id="start", tool_id="tool_a"),
            WorkflowNode(id="left", tool_id="tool_b"),
            WorkflowNode(id="right", tool_id="tool_c"),
            WorkflowNode(id="end", tool_id="tool_d"),
        ]
        edges = [
            WorkflowEdge("start", "left"),
            WorkflowEdge("start", "right"),
            WorkflowEdge("left", "end"),
            WorkflowEdge("right", "end"),
        ]
        graph = WorkflowGraphBuilder.build(nodes, edges)
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.node_results["start"].status == WorkflowStatus.COMPLETED
        assert result.node_results["left"].status == WorkflowStatus.COMPLETED
        assert result.node_results["right"].status == WorkflowStatus.COMPLETED
        assert result.node_results["end"].status == WorkflowStatus.COMPLETED

    @pytest.mark.anyio
    async def test_shared_context(self, workflow_engine):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        result = await workflow_engine.execute(graph)
        assert result.context is not None
        assert result.context.shared_data.get("a") == "a_done"

    @pytest.mark.anyio
    async def test_invalid_graph_fails_early(self, workflow_engine):
        nodes = [WorkflowNode(id="a", node_type=WorkflowNodeType.TOOL, tool_id="")]
        graph = WorkflowGraphBuilder.build(nodes, [])
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.FAILED


# ── Failure Tests ─────────────────────────────────────────────────────────

class TestWorkflowFailure:
    @pytest.mark.anyio
    async def test_failing_node(self, workflow_engine):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="failing")], [],
        )
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.FAILED
        assert result.node_results["a"].status == WorkflowStatus.FAILED

    @pytest.mark.anyio
    async def test_failure_stops_downstream(self, workflow_engine):
        nodes = [
            WorkflowNode(id="a", tool_id="failing"),
            WorkflowNode(id="b", tool_id="tool_b"),
        ]
        edges = [WorkflowEdge("a", "b")]
        graph = WorkflowGraphBuilder.build(nodes, edges)
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.FAILED
        assert result.node_results["a"].status == WorkflowStatus.FAILED
        assert result.node_results["b"].status in (WorkflowStatus.SKIPPED, WorkflowStatus.PENDING)


# ── Timeout Tests ─────────────────────────────────────────────────────────

class TestWorkflowTimeout:
    @pytest.mark.anyio
    async def test_tool_timeout(self, legacy_registry, universal_registry, event_bus):
        r = LegacyToolRegistry()
        r.register("too_slow", MockWfTool("too_slow", delay=5.0))
        universal_registry.register(ToolDefinition(
            id="too_slow", name="too_slow", description="slow",
            category=ToolCategory.FILESYSTEM,
        ))
        te = ToolExecutionEngine(r, universal_registry, event_bus)
        wfe = WorkflowExecutor(te, event_bus)
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="too_slow", timeout=0.1)], [],
        )
        result = await wfe.execute(graph, global_timeout=0.1)
        assert result.node_results["a"].status == WorkflowStatus.FAILED


# ── Cancellation Tests ────────────────────────────────────────────────────

class TestWorkflowCancellation:
    @pytest.mark.anyio
    async def test_cancellation_before_execution(self, workflow_engine):
        token = CancellationToken()
        token.cancel()
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        result = await workflow_engine.execute(graph, cancellation_token=token)
        assert result.node_results["a"].status == WorkflowStatus.CANCELLED


# ── Conditional Branching Tests ───────────────────────────────────────────

class TestConditionalBranching:
    @pytest.mark.anyio
    async def test_condition_node(self, workflow_engine):
        true_condition = lambda ctx: True
        condition_node = WorkflowNode(
            id="cond", node_type=WorkflowNodeType.CONDITION,
            condition=true_condition,
        )
        graph = WorkflowGraphBuilder.build(
            [condition_node,
             WorkflowNode(id="a", tool_id="tool_a")],
            [WorkflowEdge("cond", "a")],
        )
        result = await workflow_engine.execute(graph)
        assert result.node_results["cond"].status == WorkflowStatus.COMPLETED
        assert result.node_results["cond"].output is True


# ── Merge Node Tests ──────────────────────────────────────────────────────

class TestMergeNode:
    @pytest.mark.anyio
    async def test_merge_node(self, workflow_engine):
        nodes = [
            WorkflowNode(id="a", tool_id="tool_a"),
            WorkflowNode(id="b", tool_id="tool_b"),
            WorkflowNode(id="merge", node_type=WorkflowNodeType.MERGE),
        ]
        edges = [
            WorkflowEdge("a", "merge"),
            WorkflowEdge("b", "merge"),
        ]
        graph = WorkflowGraphBuilder.build(nodes, edges)
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.node_results["merge"].status == WorkflowStatus.COMPLETED


# ── Planner Integration Tests ─────────────────────────────────────────────

class TestPlannerIntegration:
    @pytest.mark.anyio
    async def test_plan_and_execute(self, workflow_engine):
        selection = ToolSelectionResult(selected_tools=[
            SelectedTool(
                tool=ToolDefinition(id="tool_a", name="Tool A", description="",
                                    category=ToolCategory.FILESYSTEM),
                score=1.0,
            ),
            SelectedTool(
                tool=ToolDefinition(id="tool_b", name="Tool B", description="",
                                    category=ToolCategory.FILESYSTEM),
                score=0.9,
            ),
        ])
        graph = WorkflowPlanner.plan_from_selection(
            selection,
            edges=[WorkflowEdge("tool_a", "tool_b")],
        )
        result = await workflow_engine.execute(graph)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.node_results["tool_a"].status == WorkflowStatus.COMPLETED
        assert result.node_results["tool_b"].status == WorkflowStatus.COMPLETED


# ── Event Tests ───────────────────────────────────────────────────────────

class TestWorkflowEvents:
    @pytest.mark.anyio
    async def test_publishes_started_and_completed(self, workflow_engine, event_bus):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        await workflow_engine.execute(graph)
        started = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], WorkflowStarted)
        ]
        completed = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], WorkflowCompleted)
        ]
        assert len(started) == 1
        assert len(completed) == 1

    @pytest.mark.anyio
    async def test_publishes_node_events(self, workflow_engine, event_bus):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        await workflow_engine.execute(graph)
        node_started = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], WorkflowNodeStarted)
        ]
        node_completed = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], WorkflowNodeCompleted)
        ]
        assert len(node_started) >= 1
        assert len(node_completed) >= 1

    @pytest.mark.anyio
    async def test_publishes_failed_event(self, workflow_engine, event_bus):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="failing")], [],
        )
        await workflow_engine.execute(graph)
        failed = [
            c for c in event_bus.publish.call_args_list
            if isinstance(c[0][0], WorkflowFailed)
        ]
        assert len(failed) >= 1

    @pytest.mark.anyio
    async def test_no_event_bus_does_not_crash(self, tool_engine):
        wfe = WorkflowExecutor(tool_engine, event_bus=None)
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        result = await wfe.execute(graph)
        assert result.status == WorkflowStatus.COMPLETED


# ── Health Tests ──────────────────────────────────────────────────────────

class TestWorkflowHealth:
    def test_health_defaults(self, workflow_engine):
        h = workflow_engine.health()
        assert h["status"] == "healthy"
        assert h["execution_count"] == 0
        assert h["failure_count"] == 0

    @pytest.mark.anyio
    async def test_health_after_execution(self, workflow_engine):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="tool_a")], [],
        )
        await workflow_engine.execute(graph)
        h = workflow_engine.health()
        assert h["execution_count"] == 1
        assert h["average_latency_ms"] >= 0

    @pytest.mark.anyio
    async def test_health_tracks_failures(self, workflow_engine):
        graph = WorkflowGraphBuilder.build(
            [WorkflowNode(id="a", tool_id="failing")], [],
        )
        await workflow_engine.execute(graph)
        h = workflow_engine.health()
        assert h["failure_count"] >= 1
