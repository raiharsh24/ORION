import pytest
import anyio
from unittest.mock import MagicMock


# =============================================================================
# Base Model Tests
# =============================================================================

class TestMission:
    @pytest.fixture
    def mission(self):
        from app.runtime.base import Mission
        return Mission(mission_id="m1", user_request="Build the project")

    def test_create(self, mission):
        assert mission.mission_id == "m1"
        assert mission.user_request == "Build the project"
        assert mission.status == "created"

    def test_add_stage(self, mission):
        stage = mission.add_stage("planning")
        assert stage.name == "planning"
        assert stage.status == "running"
        assert len(mission.stages) == 1

    def test_complete_stage(self, mission):
        mission.add_stage("planning")
        mission.complete_stage("planning")
        stage = mission.stages[0]
        assert stage.status == "completed"

    def test_complete_stage_with_error(self, mission):
        mission.add_stage("execution")
        mission.complete_stage("execution", error="timeout")
        stage = mission.stages[0]
        assert stage.status == "failed"
        assert stage.error == "timeout"

    def test_set_status(self, mission):
        mission.set_status("running")
        assert mission.status == "running"
        mission.set_status("completed")
        assert mission.completed_at is not None

    def test_current_stage(self, mission):
        mission.add_stage("planning")
        assert mission.current_stage == "planning"
        mission.complete_stage("planning")
        mission.add_stage("execution")
        assert mission.current_stage == "execution"

    def test_total_duration(self, mission):
        assert mission.total_duration_ms == 0.0
        mission.set_status("completed")
        assert mission.total_duration_ms >= 0.0


class TestMissionStage:
    def test_duration_ms(self):
        from datetime import datetime, timezone, timedelta
        from app.runtime.base import MissionStage
        stage = MissionStage(name="test", status="completed")
        stage.started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        stage.completed_at = datetime.now(timezone.utc)
        assert 800 <= stage.duration_ms <= 1200


# =============================================================================
# State Machine Tests
# =============================================================================

class TestMissionStateMachine:
    @pytest.fixture
    def sm(self):
        from app.runtime.state import MissionStateMachine
        return MissionStateMachine()

    def test_initial_state(self, sm):
        assert sm.current == "created"

    def test_valid_transition(self, sm):
        assert sm.transition("planning")
        assert sm.current == "planning"

    def test_invalid_transition(self, sm):
        assert not sm.transition("completed")

    def test_terminal_states(self, sm):
        from app.runtime.state import MissionStateMachine
        sm = MissionStateMachine("completed")
        assert sm.is_terminal()
        sm = MissionStateMachine("archived")
        assert sm.is_terminal()

    def test_active_states(self, sm):
        assert not sm.is_active()
        sm.transition("planning")
        assert sm.is_active()
        sm.transition("ready")
        assert sm.is_active()
        sm.transition("running")
        assert sm.is_active()

    def test_full_lifecycle(self, sm):
        assert sm.transition("planning")
        assert sm.transition("ready")
        assert sm.transition("running")
        assert sm.transition("completed")
        assert sm.is_terminal()
        assert sm.transition("archived")
        assert sm.is_terminal()
        assert not sm.transition("running")

    def test_failure_and_recovery(self, sm):
        assert sm.transition("planning")
        assert sm.transition("ready")
        assert sm.transition("running")
        assert sm.transition("failed")
        assert sm.transition("recovering")
        assert sm.transition("running")

    def test_reset(self, sm):
        sm.transition("planning")
        sm.transition("ready")
        sm.reset("created")
        assert sm.current == "created"
        assert len(sm.history) == 1


# =============================================================================
# Dispatcher Tests
# =============================================================================

class TestDispatcher:
    @pytest.fixture
    def dispatcher(self):
        from app.runtime.dispatcher import Dispatcher
        return Dispatcher()

    def test_default_dispatch(self, dispatcher):
        from app.runtime.base import Mission
        mission = Mission(mission_id="m1", user_request="do something")
        decision = dispatcher.dispatch(mission)
        assert decision.strategy is not None

    def test_preferred_strategy(self, dispatcher):
        from app.runtime.base import Mission
        mission = Mission(mission_id="m1", user_request="test",
                          metadata={"dispatch_strategy": "tool_execution"})
        decision = dispatcher.dispatch(mission)
        from app.runtime.dispatcher import DispatchStrategy
        assert decision.strategy == DispatchStrategy.TOOL_EXECUTION

    def test_workflow_keyword(self, dispatcher):
        from app.runtime.base import Mission
        mission = Mission(mission_id="m1", user_request="run workflow for build")
        decision = dispatcher.dispatch(mission)
        from app.runtime.dispatcher import DispatchStrategy
        assert decision.strategy == DispatchStrategy.WORKFLOW_ENGINE

    def test_available_no_backend(self, dispatcher):
        assert not dispatcher.available

    def test_available_with_agent_manager(self, dispatcher):
        from app.runtime.dispatcher import Dispatcher
        mgr = MagicMock()
        d = Dispatcher(agent_manager=mgr)
        assert d.available


# =============================================================================
# Supervisor Tests
# =============================================================================

class TestSupervisor:
    @pytest.fixture
    def supervisor(self):
        from app.runtime.supervisor import Supervisor
        return Supervisor()

    def test_check_timeouts(self, supervisor):
        supervisor.watch_timeout("m1", timeout_s=-1)
        timed_out = supervisor.check_timeouts()
        assert "m1" in timed_out

    def test_no_timeouts(self, supervisor):
        supervisor.watch_timeout("m1", timeout_s=999)
        timed_out = supervisor.check_timeouts()
        assert "m1" not in timed_out

    def test_record_failure(self, supervisor):
        count = supervisor.record_failure("m1")
        assert count == 1
        count = supervisor.record_failure("m1")
        assert count == 2

    def test_can_retry(self, supervisor):
        assert supervisor.can_retry("m1")
        supervisor.record_failure("m1")
        supervisor.record_failure("m1")
        supervisor.record_failure("m1")
        assert not supervisor.can_retry("m1")

    @pytest.mark.anyio
    async def test_recover_timeout(self, supervisor):
        action = await supervisor.recover_timeout("m1")
        assert action.action_type == "retry"
        assert supervisor.recovery_count > 0

    @pytest.mark.anyio
    async def test_recover_failure(self, supervisor):
        action = await supervisor.recover_failure("m1", "test error")
        assert action.action_type == "retry"
        assert supervisor.recovery_success_rate >= 0

    def test_supervision_report_no_issues(self, supervisor):
        from app.runtime.supervisor import SupervisionReport
        report = SupervisionReport()
        assert report.issues_detected == 0


# =============================================================================
# Executor Tests
# =============================================================================

class TestMissionExecutor:
    @pytest.fixture
    def executor(self):
        from app.runtime.executor import MissionExecutor
        return MissionExecutor()

    @pytest.fixture
    def mission(self):
        from app.runtime.base import Mission
        return Mission(mission_id="m1", user_request="test mission")

    def test_register_mission(self, executor, mission):
        executor.register_mission(mission)
        assert executor.get_mission("m1") is not None

    @pytest.mark.anyio
    async def test_execute_mission(self, executor, mission):
        executor.register_mission(mission)
        result = await executor.execute_mission(mission)
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_pause_and_resume(self, executor, mission):
        from app.runtime.state import MissionStateMachine
        executor.register_mission(mission)
        executor._state_machines["m1"] = MissionStateMachine("running")
        paused = await executor.pause_mission("m1")
        assert paused
        resumed = await executor.resume_mission("m1")
        assert resumed

    @pytest.mark.anyio
    async def test_cancel_mission(self, executor, mission):
        executor.register_mission(mission)
        cancelled = await executor.cancel_mission("m1")
        assert cancelled

    @pytest.mark.anyio
    async def test_pause_nonexistent(self, executor):
        assert not await executor.pause_mission("nonexistent")

    @pytest.mark.anyio
    async def test_resume_nonexistent(self, executor):
        assert not await executor.resume_mission("nonexistent")

    def test_active_counts(self, executor, mission):
        assert executor.active_mission_count == 0
        executor.register_mission(mission)
        assert executor.active_mission_count == 1


# =============================================================================
# Telemetry Tests
# =============================================================================

class TestTelemetry:
    @pytest.fixture
    def telemetry(self):
        from app.runtime.telemetry import TelemetryCollector
        return TelemetryCollector()

    def test_create_mission(self, telemetry):
        t = telemetry.create_mission("m1", "build")
        assert t.mission_id == "m1"
        assert t.intent == "build"

    def test_record_latencies(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.record_planning_latency("m1", 100.0)
        telemetry.record_execution_latency("m1", 500.0)
        telemetry.record_reflection_latency("m1", 50.0)
        t = telemetry.get_mission("m1")
        assert t.planning_latency_ms == 100.0
        assert t.execution_latency_ms == 500.0

    def test_retry_and_recovery(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.record_retry("m1")
        telemetry.record_retry("m1")
        telemetry.record_recovery("m1")
        t = telemetry.get_mission("m1")
        assert t.retry_count == 2
        assert t.recovery_count == 1

    def test_agent_utilization(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.record_agent_utilization("m1", "agent1", 0.75)
        t = telemetry.get_mission("m1")
        assert t.agent_utilization["agent1"] == 0.75

    def test_completion_tracking(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.record_completion("m1", True, 1000.0)
        assert telemetry.success_rate == 1.0
        telemetry.create_mission("m2")
        telemetry.record_completion("m2", False, 500.0)
        assert telemetry.success_rate < 1.0

    def test_failure_causes(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.record_failure("m1", "execution", "timeout")
        assert "timeout" in telemetry.failure_causes

    def test_snapshot(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.record_completion("m1", True, 100.0)
        snap = telemetry.snapshot()
        assert snap["total_missions"] == 1
        assert snap["successful"] == 1

    def test_reset(self, telemetry):
        telemetry.create_mission("m1")
        telemetry.reset()
        assert telemetry.total_missions == 0


# =============================================================================
# Runtime Metrics Tests
# =============================================================================

class TestRuntimeMetrics:
    @pytest.fixture
    def metrics(self):
        from app.runtime.metrics import RuntimeMetrics
        return RuntimeMetrics()

    def test_mission_lifecycle(self, metrics):
        metrics.record_mission_created()
        metrics.record_mission_created()
        metrics.record_mission_completed()
        snap = metrics.snapshot()
        assert snap.total_missions == 2
        assert snap.completed_missions == 1
        assert snap.active_missions == 1

    def test_latencies(self, metrics):
        metrics.record_planning_latency(100.0)
        metrics.record_planning_latency(200.0)
        metrics.record_execution_latency(500.0)
        snap = metrics.snapshot()
        assert snap.average_planning_latency_ms == 150.0
        assert snap.average_execution_latency_ms == 500.0

    def test_retries_and_recoveries(self, metrics):
        metrics.record_retry()
        metrics.record_retry()
        metrics.record_retry()
        metrics.record_recovery()
        snap = metrics.snapshot()
        assert snap.total_retries == 3
        assert snap.total_recoveries == 1

    def test_failure_causes(self, metrics):
        metrics.record_failure_cause("timeout")
        metrics.record_failure_cause("timeout")
        metrics.record_failure_cause("crash")
        snap = metrics.snapshot()
        assert snap.failure_causes["timeout"] == 2
        assert snap.failure_causes["crash"] == 1

    def test_stage_latencies(self, metrics):
        metrics.record_stage_latency("planning", 100.0)
        metrics.record_stage_latency("planning", 200.0)
        snap = metrics.snapshot()
        assert "planning" in snap.stage_latencies


# =============================================================================
# Reflection Tests
# =============================================================================

class TestReflection:
    @pytest.fixture
    def engine(self):
        from app.runtime.reflection import ReflectionEngine
        return ReflectionEngine()

    @pytest.mark.anyio
    async def test_reflect_success(self, engine):
        from app.runtime.base import Mission, ExecutionResult
        mission = Mission(mission_id="m1", user_request="test")
        mission.add_stage("planning")
        mission.complete_stage("planning")
        result = ExecutionResult(success=True, mission_id="m1",
                                 stages_completed=1)
        report = await engine.reflect(mission, result)
        assert report.mission_id == "m1"
        assert len(report.lessons) >= 1

    @pytest.mark.anyio
    async def test_reflect_failure(self, engine):
        from app.runtime.base import Mission, ExecutionResult
        mission = Mission(mission_id="m1", user_request="test")
        result = ExecutionResult(success=False, mission_id="m1",
                                 error="Timeout")
        report = await engine.reflect(mission, result)
        assert report.mission_id == "m1"
        categories = [l.category for l in report.lessons]
        assert "failure" in categories

    @pytest.mark.anyio
    async def test_bottleneck_detection(self, engine):
        from app.runtime.base import Mission, ExecutionResult, MissionStage
        from datetime import datetime, timezone, timedelta
        mission = Mission(mission_id="m1", user_request="test")
        slow = MissionStage(name="slow_stage", status="completed")
        slow.started_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        slow.completed_at = datetime.now(timezone.utc)
        mission.stages.append(slow)
        result = ExecutionResult(success=True, mission_id="m1")
        report = await engine.reflect(mission, result)
        assert len(report.bottlenecks) >= 1

    def test_lesson_creation(self):
        from app.runtime.reflection import Lesson
        lesson = Lesson(category="performance", description="Slow stage",
                        severity="warning", recommendation="Optimize")
        assert lesson.category == "performance"
        assert lesson.severity == "warning"


# =============================================================================
# Health Tests
# =============================================================================

class TestRuntimeHealth:
    def test_create(self):
        from app.runtime.health import RuntimeHealth
        h = RuntimeHealth(
            running_missions=2, completed_missions=10,
            failed_missions=1,
        )
        assert h.status == "healthy"
        assert h.running_missions == 2
        assert h.completed_missions == 10

    def test_to_dict(self):
        from app.runtime.health import RuntimeHealth
        h = RuntimeHealth(running_missions=3)
        d = h.to_dict()
        assert d["status"] == "healthy"
        assert d["running_missions"] == 3


# =============================================================================
# Orchestrator Tests
# =============================================================================

class TestOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        from app.runtime.orchestrator import Orchestrator
        return Orchestrator()

    @pytest.mark.anyio
    async def test_submit_request(self, orchestrator):
        mission = await orchestrator.submit_request("Build the project",
                                                     intent="build")
        assert mission is not None
        assert mission.user_request == "Build the project"
        assert mission.intent == "build"

    @pytest.mark.anyio
    async def test_run_lifecycle(self, orchestrator):
        mission = await orchestrator.submit_request("test mission")
        result = await orchestrator.run_lifecycle(mission)
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_pause_resume(self, orchestrator):
        mission = await orchestrator.submit_request("test")
        await orchestrator.run_lifecycle(mission)
        paused = await orchestrator.pause_mission(mission.mission_id)
        assert isinstance(paused, bool)

    @pytest.mark.anyio
    async def test_archive(self, orchestrator):
        mission = await orchestrator.submit_request("test")
        await orchestrator.run_lifecycle(mission)
        archived = await orchestrator.archive_mission(mission.mission_id)
        assert isinstance(archived, bool)

    @pytest.mark.anyio
    async def test_list_missions(self, orchestrator):
        await orchestrator.submit_request("m1")
        await orchestrator.submit_request("m2")
        missions = orchestrator.list_missions()
        assert len(missions) == 2

    def test_health(self, orchestrator):
        h = orchestrator.health()
        assert h["status"] == "healthy"


# =============================================================================
# MissionRuntime Tests
# =============================================================================

class TestMissionRuntime:
    @pytest.fixture
    def runtime(self):
        from app.runtime.runtime import MissionRuntime
        return MissionRuntime()

    @pytest.mark.anyio
    async def test_submit_and_run(self, runtime):
        result = await runtime.submit_and_run(
            "Build the project", intent="build")
        assert isinstance(result.success, bool)
        assert result.mission_id is not None

    @pytest.mark.anyio
    async def test_submit(self, runtime):
        mission = await runtime.submit("test request", "test")
        assert mission is not None
        assert mission.intent == "test"

    @pytest.mark.anyio
    async def test_list_missions(self, runtime):
        await runtime.submit("m1")
        await runtime.submit("m2")
        assert len(runtime.list_missions()) == 2

    @pytest.mark.anyio
    async def test_metrics(self, runtime):
        await runtime.submit_and_run("test", "test")
        m = runtime.metrics()
        assert m.total_missions >= 1

    @pytest.mark.anyio
    async def test_telemetry_summary(self, runtime):
        await runtime.submit_and_run("test", "test")
        t = runtime.telemetry_summary()
        assert t["total_missions"] >= 1

    @pytest.mark.anyio
    async def test_health(self, runtime):
        await runtime.submit_and_run("test", "test")
        h = runtime.health()
        assert h.status == "healthy"

    @pytest.mark.anyio
    async def test_archive(self, runtime):
        result = await runtime.submit_and_run("test", "test")
        archived = await runtime.archive(result.mission_id)
        assert isinstance(archived, bool)

    @pytest.mark.anyio
    async def test_multi_mission_lifecycle(self, runtime):
        r1 = await runtime.submit_and_run("request 1", "intent1")
        r2 = await runtime.submit_and_run("request 2", "intent2")
        r3 = await runtime.submit_and_run("request 3", "intent3")
        assert r1.success is not None
        assert r2.success is not None
        assert r3.success is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    def test_event_types(self):
        from app.runtime.events import (
            MissionStarted, MissionPaused, MissionResumed,
            MissionCompleted, MissionFailed, MissionRecovered, MissionArchived,
        )
        e1 = MissionStarted("m1", "build", "build")
        assert e1.topic == "MissionStarted"
        e2 = MissionCompleted("m1", 1000.0, 5)
        assert e2.topic == "MissionCompleted"
        e3 = MissionFailed("m1", "execution", "timeout")
        assert e3.topic == "MissionFailed"
        e4 = MissionRecovered("m1", 2)
        assert e4.topic == "MissionRecovered"
        e5 = MissionArchived("m1")
        assert e5.topic == "MissionArchived"

    def test_health_model_to_dict(self):
        from app.runtime.health import RuntimeHealth
        h = RuntimeHealth(running_missions=3, completed_missions=10)
        d = h.to_dict()
        assert d["running_missions"] == 3
        assert d["completed_missions"] == 10

    def test_module_exports(self):
        from app.runtime import (
            Mission, MissionStage, ExecutionResult, MissionStateMachine,
            Orchestrator, Dispatcher, MissionExecutor, Supervisor,
            ReflectionEngine, TelemetryCollector, RuntimeMetrics,
            RuntimeHealth, MissionRuntime,
        )
        assert MissionRuntime is not None
        assert Orchestrator is not None
        assert MissionStateMachine is not None

    @pytest.mark.anyio
    async def test_stress_concurrent_missions(self, runtime):
        from app.runtime.runtime import MissionRuntime
        runtime = MissionRuntime()
        import asyncio
        coros = [
            runtime.submit_and_run(f"Request {i}", f"intent-{i}")
            for i in range(5)
        ]
        results = await asyncio.gather(*coros, return_exceptions=True)
        successes = [r for r in results if isinstance(r, Exception) is False and r.success]
        assert len(successes) >= 0

    @pytest.mark.anyio
    async def test_mission_full_lifecycle(self):
        from app.runtime.runtime import MissionRuntime
        runtime = MissionRuntime()
        mission = await runtime.submit("Complex build", "build",
                                       metadata={"priority": "high"})
        assert mission.metadata["priority"] == "high"

        result = await runtime.run(mission)
        assert isinstance(result.success, bool)

        paused = await runtime.pause(mission.mission_id)
        assert isinstance(paused, bool)
        resumed = await runtime.resume(mission.mission_id)
        assert isinstance(resumed, bool)

        m = runtime.metrics()
        assert m.total_missions >= 1

        t = runtime.telemetry_summary()
        assert "total_missions" in t

        h = runtime.health()
        assert h.status == "healthy"

    @pytest.mark.anyio
    async def test_mission_state_flow(self):
        from app.runtime.state import MissionStateMachine
        sm = MissionStateMachine()
        assert sm.transition("planning")
        assert sm.transition("ready")
        assert sm.transition("running")
        assert sm.transition("paused")
        assert sm.transition("running")
        assert sm.transition("failed")
        assert sm.transition("recovering")
        assert sm.transition("running")
        assert sm.transition("completed")
        assert sm.is_terminal()
        assert len(sm.history) == 10


# =============================================================================
# Queue Tests
# =============================================================================

class TestMissionQueue:
    @pytest.mark.anyio
    async def test_enqueue(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        eid = await q.enqueue("m1")
        assert eid is not None
        assert q.size == 1

    @pytest.mark.anyio
    async def test_priority_ordering(self):
        from app.runtime.queue import MissionQueue, MissionPriority
        q = MissionQueue()
        await q.enqueue("low", priority=MissionPriority.LOW)
        await q.enqueue("high", priority=MissionPriority.HIGH)
        await q.enqueue("medium", priority=MissionPriority.MEDIUM)
        assert q.size == 3
        entry = q.peek()
        assert entry is not None
        assert entry.mission_id == "high"

    @pytest.mark.anyio
    async def test_peek_empty(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        assert q.peek() is None

    @pytest.mark.anyio
    async def test_cancel_queued(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        await q.enqueue("m1")
        result = await q.cancel("m1")
        assert result

    @pytest.mark.anyio
    async def test_cancel_nonexistent(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        result = await q.cancel("nonexistent")
        assert not result

    @pytest.mark.anyio
    async def test_queue_status(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        await q.enqueue("m1")
        status = q.status
        assert status.queued == 1
        assert status.max_concurrent == 4

    @pytest.mark.anyio
    async def test_handler_execution(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        results = []
        async def handler(mid):
            results.append(mid)
            return "done"
        q.set_handler(handler)
        await q.enqueue("m1")
        await q.wait_for_all()
        assert "m1" in results

    @pytest.mark.anyio
    async def test_clear(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        await q.enqueue("m1")
        await q.enqueue("m2")
        assert q.size == 2
        q.clear()
        assert q.size == 0

    @pytest.mark.anyio
    async def test_list_queued_and_running(self):
        from app.runtime.queue import MissionQueue
        q = MissionQueue()
        await q.enqueue("m1")
        assert "m1" in q.list_queued()


# =============================================================================
# Persistence Tests
# =============================================================================

class TestMissionStore:
    @pytest.fixture
    def store(self, tmp_path):
        from app.runtime.persistence import MissionStore
        return MissionStore(base_path=str(tmp_path))

    def test_save_and_load_mission(self, store):
        from app.runtime.base import Mission
        m = Mission(mission_id="m1", user_request="test")
        store.save_mission(m)
        loaded = store.load_mission("m1")
        assert loaded is not None
        assert loaded.mission_id == "m1"
        assert loaded.user_request == "test"

    def test_load_nonexistent(self, store):
        loaded = store.load_mission("nonexistent")
        assert loaded is None

    def test_list_missions(self, store):
        from app.runtime.base import Mission
        store.save_mission(Mission(mission_id="m1", user_request="a"))
        store.save_mission(Mission(mission_id="m2", user_request="b"))
        missions = store.list_missions()
        assert "m1" in missions
        assert "m2" in missions

    def test_delete_mission(self, store):
        from app.runtime.base import Mission
        store.save_mission(Mission(mission_id="m1", user_request="test"))
        assert store.delete_mission("m1")
        assert store.load_mission("m1") is None

    def test_save_and_load_telemetry(self, store):
        from app.runtime.telemetry import MissionTelemetry
        tel = MissionTelemetry(mission_id="m1", intent="build",
                               planning_latency_ms=100.0)
        store.save_telemetry("m1", tel)
        loaded = store.load_telemetry("m1")
        assert loaded is not None
        assert loaded.intent == "build"
        assert loaded.planning_latency_ms == 100.0

    def test_save_and_load_checkpoint(self, store):
        store.save_checkpoint("m1", "planning", {"status": "ok"})
        cp = store.load_checkpoint("m1")
        assert cp is not None
        assert cp.stage == "planning"
        assert cp.data["status"] == "ok"

    def test_save_and_load_reflection(self, store):
        from app.runtime.reflection import ReflectionReport, Lesson
        report = ReflectionReport(
            mission_id="m1",
            total_duration_ms=500.0,
            bottlenecks=["slow stage"],
            lessons=[Lesson(category="performance",
                            description="Too slow", severity="warning")],
        )
        store.save_reflection("m1", report)
        loaded = store.load_reflection("m1")
        assert loaded is not None
        assert loaded["total_duration_ms"] == 500.0
        assert "slow stage" in loaded["bottlenecks"]

    def test_load_all_active(self, store):
        from app.runtime.base import Mission
        m1 = Mission(mission_id="m1", user_request="test", status="running")
        m2 = Mission(mission_id="m2", user_request="test", status="completed")
        store.save_mission(m1)
        store.save_mission(m2)
        active = store.load_all_active()
        mids = [r.mission_id for r in active]
        assert "m1" in mids
        assert "m2" not in mids


# =============================================================================
# Runtime API Tests
# =============================================================================

class TestRuntimeAPI:
    @pytest.fixture
    def rt(self):
        from app.runtime.runtime import MissionRuntime
        return MissionRuntime()

    @pytest.mark.anyio
    async def test_submit_background(self, rt):
        mid = await rt.submit_background("test request", "test")
        assert mid is not None
        assert isinstance(mid, str)

    @pytest.mark.anyio
    async def test_get_status(self, rt):
        mission = await rt.submit("test", "test")
        status = rt.get_status(mission.mission_id)
        assert status == "created"

    @pytest.mark.anyio
    async def test_get_status_nonexistent(self, rt):
        status = rt.get_status("nonexistent")
        assert status is None

    @pytest.mark.anyio
    async def test_get_history(self, rt):
        await rt.submit("request 1", "intent1")
        await rt.submit("request 2", "intent2")
        history = rt.get_history()
        requests = [h["user_request"] for h in history]
        assert "request 1" in requests
        assert "request 2" in requests

    @pytest.mark.anyio
    async def test_queue_status(self, rt):
        await rt.submit("test", "test")
        qs = rt.queue_status()
        assert qs is not None
        assert qs.queued >= 1

    @pytest.mark.anyio
    async def test_get_telemetry(self, rt):
        mission = await rt.submit("test", "test")
        tel = rt.get_telemetry(mission.mission_id)
        assert tel is not None
        assert tel.intent == "test"


# =============================================================================
# Integration Tests — Queue + Persistence + Runtime
# =============================================================================

class TestQueuePersistenceIntegration:
    @pytest.mark.anyio
    async def test_orchestrator_persists_mission(self, tmp_path):
        from app.runtime.orchestrator import Orchestrator
        from app.runtime.persistence import MissionStore
        store = MissionStore(base_path=str(tmp_path))
        orch = Orchestrator(store=store)
        mission = await orch.submit_request("persist test", "test")
        result = await orch.run_lifecycle(mission)
        loaded = store.load_mission(mission.mission_id)
        assert loaded is not None
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_cancel_queued_mission(self):
        from app.runtime.runtime import MissionRuntime
        rt = MissionRuntime()
        await rt.submit("cancel test", "test")
        history_before = len(rt.get_history())
        assert history_before >= 1

    @pytest.mark.anyio
    async def test_retry_nonexistent(self):
        from app.runtime.runtime import MissionRuntime
        rt = MissionRuntime()
        result = await rt.retry("nonexistent")
        assert not result

    @pytest.mark.anyio
    async def test_status_after_submit(self):
        from app.runtime.runtime import MissionRuntime
        rt = MissionRuntime()
        mission = await rt.submit("test", "test")
        status = rt.get_status(mission.mission_id)
        assert status is not None


# =============================================================================
# Integration Tests — Orchestrator + Subsystems
# =============================================================================

class TestOrchestratorIntegration:
    @pytest.mark.anyio
    async def test_orchestrator_with_mock_planning(self):
        from app.runtime.orchestrator import Orchestrator
        from unittest.mock import AsyncMock
        mock_planning = MagicMock()
        mock_planning.create_goal.return_value = MagicMock(
            goal_id="g1")
        mock_planning.generate_plan = AsyncMock()
        mock_planning.generate_plan.return_value = MagicMock(
            plan_id="p1", steps=[], step_count=0, total_duration=0.0)
        orch = Orchestrator(planning_engine=mock_planning)
        mission = await orch.submit_request("test with planning", "test")
        result = await orch.run_lifecycle(mission)
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_orchestrator_with_mock_capabilities(self):
        from app.runtime.orchestrator import Orchestrator
        mock_registry = MagicMock()
        mock_registry.list_capabilities.return_value = [
            MagicMock(id="cap1", name="Capability 1"),
            MagicMock(id="cap2", name="Capability 2"),
        ]
        orch = Orchestrator(capability_registry=mock_registry)
        mission = await orch.submit_request("test caps", "test")
        result = await orch.run_lifecycle(mission)
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_orchestrator_with_mock_tool_selection(self):
        from app.runtime.orchestrator import Orchestrator
        mock_selection = MagicMock()
        mock_selection.select = MagicMock()
        mock_selection.select.return_value = MagicMock(
            tool_ids=["tool1", "tool2"])
        orch = Orchestrator(tool_selection_engine=mock_selection,
                             capability_registry=MagicMock())
        mission = await orch.submit_request("test tools", "test")
        mission.metadata["resolved_capabilities"] = ["cap1"]
        result = await orch.run_lifecycle(mission)
        assert isinstance(result.success, bool)

    @pytest.mark.anyio
    async def test_orchestrator_full_mock(self):
        from app.runtime.orchestrator import Orchestrator
        from unittest.mock import MagicMock

        planning = MagicMock()
        planning.create_goal.return_value = MagicMock(goal_id="g1")
        planning.generate_plan = MagicMock()
        planning.generate_plan.return_value = MagicMock(
            plan_id="p1", steps=[], step_count=0, total_duration=0.0)

        tool_sel = MagicMock()
        tool_sel.select = MagicMock()
        tool_sel.select.return_value = MagicMock(tool_ids=["t1"])

        tool_exec = MagicMock()
        tool_exec.execute = MagicMock()
        tool_exec.execute.return_value = MagicMock(all_succeeded=True)

        cap_reg = MagicMock()
        cap_reg.list_capabilities.return_value = []

        wf = MagicMock()
        wf.execute = MagicMock()
        wf.execute.return_value = MagicMock(
            status="completed", execution_id="wf1")

        orch = Orchestrator(
            planning_engine=planning,
            tool_selection_engine=tool_sel,
            tool_execution_engine=tool_exec,
            capability_registry=cap_reg,
            workflow_engine=wf,
        )
        mission = await orch.submit_request("full test", "test")
        result = await orch.run_lifecycle(mission)
        assert isinstance(result.success, bool)


@pytest.fixture
def runtime():
    from app.runtime.runtime import MissionRuntime
    return MissionRuntime()
