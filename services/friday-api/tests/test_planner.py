import asyncio
import pytest
from unittest.mock import MagicMock, patch

from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.planner.pipeline_graph import PipelineGraph
from app.planner.rules import PlanningRules
from app.planner.planner import DynamicPipelinePlanner
from app.planner.execution_plan import ExecutionPlan


@pytest.fixture
def event_bus():
    return EventBus()


def test_pipeline_graph_topological_sort():
    graph = PipelineGraph()
    graph.add_node("intent")
    graph.add_node("strategy")
    graph.add_node("extraction")
    graph.add_node("ranking")
    graph.add_node("assembly")

    graph.add_edge("intent", "strategy")
    graph.add_edge("strategy", "extraction")
    graph.add_edge("extraction", "ranking")
    graph.add_edge("ranking", "assembly")

    # Topological order of all nodes
    order = graph.get_stages_ordered({"intent", "strategy", "extraction", "ranking", "assembly"})
    assert order == ["intent", "strategy", "extraction", "ranking", "assembly"]

    # Topological order of subset (skipping extraction/ranking)
    subset_order = graph.get_stages_ordered({"intent", "strategy", "assembly"})
    assert subset_order == ["intent", "strategy", "assembly"]


def test_planning_rules_math():
    # Math questions skip extraction, ranking, validation, compression
    res = PlanningRules.evaluate(
        user_query="What is 2 + 2?",
        intent_type="math",
        strategy_config=None,
        cache_state={},
        snapshot_available=False,
        recommendations=[],
    )
    assert "extraction" not in res["stages"]
    assert "ranking" not in res["stages"]
    assert "validation" not in res["stages"]
    assert "compression" not in res["stages"]
    assert "assembly" in res["stages"]
    assert res["cache_probability"] == 1.0


def test_planning_rules_desktop():
    res = PlanningRules.evaluate(
        user_query="click on the start menu button",
        intent_type="desktop",
        strategy_config=None,
        cache_state={},
        snapshot_available=False,
        recommendations=[],
    )
    assert "extraction" in res["stages"]
    assert res["enabled_extractors"] == ["desktop_extractor"]


def test_planning_rules_mission():
    res = PlanningRules.evaluate(
        user_query="run the mission to deploy application",
        intent_type="mission",
        strategy_config=None,
        cache_state={},
        snapshot_available=False,
        recommendations=[],
    )
    assert "extraction" in res["stages"]
    assert set(res["enabled_extractors"]) == {
        "mission_extractor", "workflow_extractor", "memory_extractor", "knowledge_extractor"
    }


def test_planning_rules_early_exit_on_cache():
    # All extractors are cached (cache hit), snapshot is available
    res = PlanningRules.evaluate(
        user_query="how is the project progression?",
        intent_type="conversation",
        strategy_config=MagicMock(extractors=["memory_extractor", "knowledge_extractor"]),
        cache_state={"memory_extractor": True, "knowledge_extractor": True},
        snapshot_available=True,
        recommendations=[],
    )
    assert res["early_exit"] is True
    assert "extraction" not in res["stages"]
    assert "ranking" not in res["stages"]
    assert "validation" not in res["stages"]
    assert "incremental_update" in res["stages"]
    assert "assembly" in res["stages"]


@pytest.mark.anyio
async def test_dynamic_pipeline_planner_e2e(event_bus):
    planner = DynamicPipelinePlanner(event_bus=event_bus)
    await planner.start()

    events_captured = []
    event_bus.subscribe("PlanCreated", lambda e: events_captured.append("created"))
    event_bus.subscribe("StageSkipped", lambda e: events_captured.append("skipped"))
    event_bus.subscribe("PipelineOptimized", lambda e: events_captured.append("optimized"))
    event_bus.subscribe("PlanExecuted", lambda e: events_captured.append("executed"))

    # Test query that triggers optimization recommendations (e.g. skip expensive)
    # We patch kernel lookup or pass recommendations directly inside mock
    with patch("app.kernel.kernel.FridayKernel.get_instance") as mock_kernel:
        mock_instance = MagicMock()
        mock_kernel.return_value = mock_instance
        
        # Mock services
        mock_optimizer = MagicMock()
        mock_rec = MagicMock(action="skip_expensive_extractors")
        mock_optimizer._recommendations = [mock_rec]
        mock_instance.get_service.side_effect = lambda name: {
            "optimizer": mock_optimizer,
            "intent_analyzer": None,
            "strategy_manager": None,
            "incremental_context_manager": None,
            "context_cache": None,
        }.get(name)

        plan = await planner.plan("What is 5 + 5?", session_id="sess_123")
        
        assert isinstance(plan, ExecutionPlan)
        assert plan.session_id == "sess_123"
        assert "assembly" in plan.stages
        # Verify knowledge_extractor is skipped because of optimizer recommendations
        assert "knowledge_extractor" not in plan.enabled_extractors

        # Record pipeline execution
        accuracy = await planner.record_execution(plan.plan_id, plan.stages, 45.0)
        assert accuracy == 1.0

    await asyncio.sleep(0.1)

    assert "created" in events_captured
    assert "skipped" in events_captured
    assert "optimized" in events_captured
    assert "executed" in events_captured

    health = planner.health()
    assert health["status"] == "HEALTHY"
    assert health["details"]["plans_created"] == 1

    await planner.shutdown()
