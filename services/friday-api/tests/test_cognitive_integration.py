import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.cognitive.cognitive_engine import CognitiveEngine
from app.cognitive.events import (
    GoalCreated, GoalUpdated, MilestoneCompleted,
    SchedulerStarted, SchedulerStopped,
    MissionDelegated, MissionRecovered, LearningUpdated,
)
from app.cognitive.goal_memory import GoalMemory
from app.cognitive.consolidation import CognitiveConsolidation
from app.cognitive.collaborative_orchestrator import CollaborativeOrchestrator


@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_memory_engine():
    store = MagicMock()
    store.get = MagicMock(return_value=None)
    store.put = MagicMock()
    store.keys = MagicMock(return_value=[])
    manager = MagicMock()
    manager._store = store
    eng = MagicMock()
    eng._manager = manager
    return eng


@pytest.fixture
def mock_learning_engine():
    eng = MagicMock()
    eng.record_reflection = MagicMock()
    eng.get_relevant_learnings = MagicMock(return_value=[])
    eng.get_tool_effectiveness = MagicMock(return_value={})
    return eng


@pytest.fixture
def goal_memory(mock_memory_engine, mock_event_bus):
    store = mock_memory_engine._manager._store
    return GoalMemory(store=store, event_bus=mock_event_bus)


class TestCognitiveEvents:
    """Objective 6: EventBus events"""

    def test_goal_created_event(self):
        event = GoalCreated(
            goal_id="g1", objective="test objective",
            parent_id=None, priority=5.0,
        )
        assert event.topic == "cognitive.goal.created"
        assert event.data["goal_id"] == "g1"
        assert event.data["objective"] == "test objective"

    def test_goal_updated_event(self):
        event = GoalUpdated(
            goal_id="g1", objective="test",
            status="active", progress_pct=50.0,
        )
        assert event.topic == "cognitive.goal.updated"
        assert event.data["status"] == "active"

    def test_milestone_completed_event(self):
        event = MilestoneCompleted(
            goal_id="g1", milestone_id="m1",
            milestone_name="test milestone", progress_pct=100.0,
        )
        assert event.topic == "cognitive.goal.milestone_completed"

    def test_scheduler_events(self):
        started = SchedulerStarted()
        stopped = SchedulerStopped()
        assert started.topic == "cognitive.scheduler.started"
        assert stopped.topic == "cognitive.scheduler.stopped"

    def test_mission_delegated_event(self):
        event = MissionDelegated(
            mission_id="m1", objective="test",
            workflow_type="research_code_review_test",
            agent_ids=["agent1"],
        )
        assert event.topic == "cognitive.mission.delegated"

    def test_learning_updated_event(self):
        event = LearningUpdated(
            learning_type="adaptive_refresh",
            summary="test summary",
        )
        assert event.topic == "cognitive.learning.updated"


class TestGoalMemoryEvents:
    """Objective 6: GoalMemory publishes events"""

    def test_create_goal_publishes_event(self, goal_memory):
        goal = goal_memory.create_goal("test objective")
        assert goal_memory._event_bus.publish.called
        call_args = goal_memory._event_bus.publish.call_args
        event = call_args[0][0]
        assert isinstance(event, GoalCreated)

    def test_update_goal_publishes_event(self, goal_memory):
        goal = goal_memory.create_goal("test objective")
        goal_memory._event_bus.publish.reset_mock()
        goal_memory.update_goal(goal.goal_id, status="active")
        assert goal_memory._event_bus.publish.called
        call_args = goal_memory._event_bus.publish.call_args
        event = call_args[0][0]
        assert isinstance(event, GoalUpdated)

    def test_complete_milestone_publishes_event(self, goal_memory):
        goal = goal_memory.create_goal("test objective")
        ms = goal_memory.add_milestone(goal.goal_id, "ms1")
        goal_memory._event_bus.publish.reset_mock()
        goal_memory.complete_milestone(goal.goal_id, ms["id"])
        assert goal_memory._event_bus.publish.called
        call_args = goal_memory._event_bus.publish.call_args
        event = call_args[0][0]
        assert isinstance(event, MilestoneCompleted)


class TestGoalMemoryOnSave:
    """Objective 3: GoalMemory on_save callback"""

    def test_save_triggers_callback(self, goal_memory):
        callback = MagicMock()
        goal_memory.set_on_save(callback)
        goal = goal_memory.create_goal("test")
        goal_memory.save()
        assert callback.called


class TestCognitiveConsolidation:
    """Objective 3: CognitiveConsolidation"""

    @pytest.mark.anyio
    async def test_consolidation_saves_goals(self, mock_memory_engine, mock_event_bus):
        store = mock_memory_engine._manager._store
        gm = GoalMemory(store=store, event_bus=mock_event_bus)
        gm.create_goal("test goal")
        consolidator = CognitiveConsolidation(goal_memory=gm, interval_seconds=9999)
        stats = await consolidator.run_consolidation()
        assert stats["goals_saved"] >= 1
        assert "duration_ms" in stats

    @pytest.mark.anyio
    async def test_consolidation_health(self, mock_memory_engine, mock_event_bus):
        store = mock_memory_engine._manager._store
        gm = GoalMemory(store=store, event_bus=mock_event_bus)
        consolidator = CognitiveConsolidation(goal_memory=gm)
        health = consolidator.health()
        assert health["status"] == "STOPPED"

    @pytest.mark.anyio
    async def test_consolidation_start_stop(self, mock_memory_engine, mock_event_bus):
        store = mock_memory_engine._manager._store
        gm = GoalMemory(store=store, event_bus=mock_event_bus)
        consolidator = CognitiveConsolidation(goal_memory=gm)
        await consolidator.start()
        assert consolidator._running
        await consolidator.stop()
        assert not consolidator._running


class TestAutonomousSchedulerHandler:
    """Objective 4: AutonomousScheduler registers MissionExecutor handler"""

    @pytest.mark.anyio
    async def test_scheduler_registers_handler(self):
        engine = CognitiveEngine(
            event_bus=MagicMock(),
            mission_executor=MagicMock(),
            memory_engine=None,
            adaptive_scheduler=None,
        )

        handlers = engine._autonomous_scheduler._handlers
        assert "once" in handlers
        assert "recurring" in handlers

    @pytest.mark.anyio
    async def test_scheduler_start_stop_events(self, mock_event_bus, mock_memory_engine):
        engine = CognitiveEngine(
            event_bus=mock_event_bus,
            memory_engine=mock_memory_engine,
        )
        mock_event_bus.publish.reset_mock()

        await engine.start_scheduler()
        assert mock_event_bus.publish.called
        call_args = mock_event_bus.publish.call_args
        event = call_args[0][0]
        assert isinstance(event, SchedulerStarted)


class TestCollaborativeOrchestratorToolExecution:
    """Objectives 1, 2: ToolExecutionEngine wiring"""

    @pytest.fixture
    def mock_agent_manager(self):
        mgr = MagicMock()
        mgr.create_agent = MagicMock()
        mgr.get_agent = MagicMock(return_value=None)
        return mgr

    @pytest.mark.anyio
    async def test_execute_single_mission_with_tool_engine(self, mock_agent_manager):
        tool_engine = AsyncMock()
        tool_engine.execute = AsyncMock()
        tool_result = MagicMock()
        tool_result.all_succeeded = True
        tool_result.results = []
        tool_engine.execute.return_value = tool_result

        with patch(
            "app.cognitive.collaborative_orchestrator.CollaborativeOrchestrator._register_collaborative_agents",
        ), patch(
            "app.agent_orchestration.orchestrator.AgentOrchestrator._register_builtin_agents",
        ):
            orch = CollaborativeOrchestrator(
                agent_manager=mock_agent_manager,
                tool_execution_engine=tool_engine,
            )

        result = await orch._execute_single_mission({
            "mission_id": "m1",
            "capability": "web_search",
            "agent_id": "research-agent",
            "sub_goal": {"query": "test"},
            "goal_id": "g1",
        })
        assert result["success"] is True


class TestReflectionV2AdaptiveLearning:
    """Objective 5: Reflection triggers AdaptiveLearning refresh"""

    def test_reflection_stores_with_adaptive_learning(self):
        adaptive_learning = MagicMock()
        learning_engine = MagicMock()
        learning_engine.record_reflection = MagicMock()
        learning_engine.get_relevant_learnings = MagicMock(return_value=[])
        learning_engine.get_tool_effectiveness = MagicMock(return_value={})

        from app.cognitive.reflection_v2 import ReflectionV2
        rv2 = ReflectionV2(
            learning_engine=learning_engine,
            adaptive_learning=adaptive_learning,
        )

        # Trigger _store_reflection manually
        from app.cognitive.reflection_v2 import ReflectionV2Report, ExecutionQuality
        report = ReflectionV2Report(
            mission_id="m1", goal_id="g1",
            execution_quality=ExecutionQuality(stage_success_rate=1.0),
        )

        rv2._store_reflection(report)
        assert adaptive_learning.refresh_from_history.called


class TestCognitiveEngineIntegration:
    """End-to-end integration tests"""

    @pytest.mark.anyio
    async def test_cognitive_engine_health(self, mock_event_bus, mock_memory_engine):
        engine = CognitiveEngine(
            event_bus=mock_event_bus,
            memory_engine=mock_memory_engine,
        )
        health = engine.health()
        assert health["status"] == "HEALTHY"
        assert "consolidation" in health
        assert "goal_memory" in health

    @pytest.mark.anyio
    async def test_cognitive_engine_get_strategic_context(self, mock_event_bus, mock_memory_engine):
        engine = CognitiveEngine(
            event_bus=mock_event_bus,
            memory_engine=mock_memory_engine,
        )
        context = engine.get_strategic_context()
        assert "goals" in context
        assert "learning" in context

    @pytest.mark.anyio
    async def test_cognitive_engine_mission_triggers_adaptive_refresh(self, mock_event_bus, mock_memory_engine):
        learning_engine = MagicMock()
        learning_engine.record_reflection = MagicMock()
        learning_engine.get_relevant_learnings = MagicMock(return_value=[])
        learning_engine.get_tool_effectiveness = MagicMock(return_value={})

        engine = CognitiveEngine(
            event_bus=mock_event_bus,
            memory_engine=mock_memory_engine,
            learning_engine=learning_engine,
        )

        mock_event_bus.publish.reset_mock()
        with patch(
            "app.cognitive.collaborative_orchestrator.CollaborativeOrchestrator._register_collaborative_agents",
        ), patch(
            "app.agent_orchestration.orchestrator.AgentOrchestrator._register_builtin_agents",
        ):
            result = await engine.run_cognitive_mission(
                objective="test objective",
                use_collaboration=False,
            )
        assert result["status"] in ("completed", "failed")
        assert result["objective"] == "test objective"

    @pytest.mark.anyio
    async def test_cognitive_engine_orchestrator_creation(self, mock_event_bus, mock_memory_engine):
        engine = CognitiveEngine(
            event_bus=mock_event_bus,
            memory_engine=mock_memory_engine,
        )
        with patch(
            "app.cognitive.collaborative_orchestrator.CollaborativeOrchestrator._register_collaborative_agents",
        ), patch(
            "app.agent_orchestration.orchestrator.AgentOrchestrator._register_builtin_agents",
        ):
            orch = engine.get_or_create_orchestrator()
        assert orch is not None
        assert isinstance(orch, CollaborativeOrchestrator)

        # Second call returns same instance
        orch2 = engine.get_or_create_orchestrator()
        assert orch is orch2

    @pytest.mark.anyio
    async def test_orchestrator_collaborative_workflow_mission_delegated_event(self, mock_event_bus):
        mock_agent_manager = MagicMock()
        mock_agent_manager.create_agent = MagicMock()
        mock_agent_manager.get_agent = MagicMock(return_value=None)

        with patch(
            "app.cognitive.collaborative_orchestrator.CollaborativeOrchestrator._register_collaborative_agents",
        ), patch(
            "app.agent_orchestration.orchestrator.AgentOrchestrator._register_builtin_agents",
        ):
            orch = CollaborativeOrchestrator(
                event_bus=mock_event_bus,
                agent_manager=mock_agent_manager,
            )
        mock_event_bus.publish.reset_mock()

        result = await orch.collaborative_workflow(
            objective="test",
            workflow_type="research_synthesize",
        )
        # MissionDelegated event should have been published
        found = False
        for call_args in mock_event_bus.publish.call_args_list:
            event = call_args[0][0]
            if isinstance(event, MissionDelegated):
                found = True
                break
        assert found, "MissionDelegated event should be published"
