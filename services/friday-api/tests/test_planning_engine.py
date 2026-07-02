import pytest
import anyio
import tempfile
import shutil
import time
from datetime import datetime, timezone, timedelta


# =============================================================================
# Goal Tests
# =============================================================================

class TestGoal:
    @pytest.fixture
    def goal(self):
        from app.planning.goal import Goal
        return Goal(
            goal_id="g1", name="Test Goal",
            description="A test goal", priority=7.0,
        )

    def test_create(self, goal):
        assert goal.goal_id == "g1"
        assert goal.name == "Test Goal"
        assert goal.priority == 7.0
        assert goal.status == "active"

    def test_add_child(self, goal):
        goal.add_child("c1")
        goal.add_child("c2")
        assert "c1" in goal.child_goal_ids
        assert "c2" in goal.child_goal_ids
        assert len(goal.child_goal_ids) == 2

    def test_status_properties(self, goal):
        assert goal.is_active
        assert not goal.is_completed
        assert not goal.is_failed
        goal.status = "completed"
        assert goal.is_completed

    def test_is_overdue(self, goal):
        assert not goal.is_overdue
        goal.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
        assert goal.is_overdue
        goal.deadline = datetime.now(timezone.utc) + timedelta(hours=1)
        assert not goal.is_overdue

    def test_parent_child(self):
        from app.planning.goal import Goal
        parent = Goal(goal_id="p1", name="Parent")
        child = Goal(goal_id="c1", name="Child", parent_goal_id="p1")
        parent.add_child("c1")
        assert child.parent_goal_id == "p1"
        assert "c1" in parent.child_goal_ids


# =============================================================================
# Action Tests
# =============================================================================

class TestAction:
    def test_create(self):
        from app.planning.action import Action
        a = Action("build", "Build", "Build the project",
                   required_capabilities=["code_generation"])
        assert a.action_id == "build"
        assert a.name == "Build"
        assert "code_generation" in a.required_capabilities


# =============================================================================
# ActionGraph Tests
# =============================================================================

class TestActionGraph:
    @pytest.fixture
    def graph(self):
        from app.planning.graph import ActionGraph
        from app.planning.base import PlanStep
        g = ActionGraph()
        g.add_step(PlanStep(step_id="a", action_id="act1", estimated_duration=1.0))
        g.add_step(PlanStep(step_id="b", action_id="act2", estimated_duration=2.0))
        g.add_step(PlanStep(step_id="c", action_id="act3", estimated_duration=3.0))
        g.add_step(PlanStep(step_id="d", action_id="act4", estimated_duration=1.0))
        return g

    def test_add_step(self, graph):
        assert graph.step_count == 4

    def test_dependencies(self, graph):
        graph.add_dependency("b", "a")
        graph.add_dependency("c", "a")
        graph.add_dependency("d", "b")
        deps_b = graph.get_dependencies("b")
        assert "a" in deps_b
        deps_d = graph.get_dependencies("d")
        assert "b" in deps_d

    def test_detect_cycles_no_cycle(self, graph):
        graph.add_dependency("b", "a")
        graph.add_dependency("c", "b")
        assert not graph.has_cycles()

    def test_detect_cycles_has_cycle(self, graph):
        graph.add_dependency("a", "b")
        graph.add_dependency("b", "c")
        graph.add_dependency("c", "a")
        assert graph.has_cycles()
        cycles = graph.detect_cycles()
        assert len(cycles) > 0

    def test_topological_sort(self, graph):
        graph.add_dependency("b", "a")
        graph.add_dependency("c", "b")
        sorted_steps = graph.topological_sort()
        ids = [s.step_id for s in sorted_steps]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_topological_sort_with_parallel(self, graph):
        graph.add_dependency("c", "a")
        graph.add_dependency("c", "b")
        sorted_steps = graph.topological_sort()
        ids = [s.step_id for s in sorted_steps]
        assert ids.index("a") < ids.index("c")
        assert ids.index("b") < ids.index("c")

    def test_parallel_batches(self, graph):
        graph.add_dependency("c", "a")
        graph.add_dependency("c", "b")
        graph.add_dependency("d", "c")
        batches = graph.get_parallel_batches()
        assert len(batches) >= 3

    def test_critical_path(self, graph):
        graph.add_dependency("b", "a")
        graph.add_dependency("c", "b")
        graph.add_dependency("d", "c")
        path = graph.get_critical_path()
        assert len(path) >= 2
        assert path[0].step_id == "a"

    def test_critical_path_longest(self, graph):
        graph.add_dependency("b", "a")
        graph.add_dependency("d", "b")
        path = graph.get_critical_path()
        critical_ids = [s.step_id for s in path]
        assert "a" in critical_ids
        assert "b" in critical_ids

    def test_max_depth(self, graph):
        graph.add_dependency("b", "a")
        graph.add_dependency("c", "b")
        graph.add_dependency("d", "c")
        assert graph.get_max_depth() >= 3


# =============================================================================
# Heuristics Tests
# =============================================================================

class TestHeuristics:
    @pytest.fixture
    def scorer(self):
        from app.planning.heuristics import HeuristicScorer
        return HeuristicScorer()

    @pytest.fixture
    def simple_plan(self):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p1", goal_id="g1", goal_name="test")
        plan.add_step(PlanStep(step_id="s1", action_id="a1", estimated_cost=1.0, estimated_duration=1.0))
        plan.add_step(PlanStep(step_id="s2", action_id="a2", dependencies=["s1"], estimated_cost=2.0, estimated_duration=2.0))
        plan.add_step(PlanStep(step_id="s3", action_id="a3", dependencies=["s2"], estimated_cost=3.0, estimated_duration=3.0))
        return plan

    def test_scorer_produces_scores(self, scorer, simple_plan):
        scores = scorer.score(simple_plan)
        assert scores.complexity > 0
        assert scores.cost > 0
        assert scores.latency > 0
        assert scores.total > 0

    def test_complexity_increases_with_steps(self, scorer, simple_plan):
        from app.planning.base import Plan, PlanStep
        small = Plan(plan_id="p2", goal_id="g1")
        small.add_step(PlanStep(step_id="s1", action_id="a1"))
        large = Plan(plan_id="p3", goal_id="g1")
        for i in range(10):
            large.add_step(PlanStep(step_id=f"s{i}", action_id="a1"))
        assert scorer.score(small).complexity < scorer.score(large).complexity

    def test_empty_plan_zero_risk(self, scorer):
        from app.planning.base import Plan
        empty = Plan(plan_id="empty", goal_id="g1")
        scores = scorer.score(empty)
        assert scores.risk == 0

    def test_normalize_clamps_values(self, scorer):
        assert scorer._normalize(-10, 0, 100) == 0
        assert scorer._normalize(200, 0, 100) == 1


# =============================================================================
# Constraint Engine Tests
# =============================================================================

class TestConstraintEngine:
    @pytest.fixture
    def engine(self):
        from app.planning.constraints import ConstraintEngine
        return ConstraintEngine()

    @pytest.fixture
    def valid_plan(self):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p1", goal_id="g1")
        step = PlanStep(step_id="s1", action_id="a1", agent_id="agent1")
        plan.add_step(step)
        return plan

    def test_valid_plan_passes(self, engine, valid_plan):
        result = engine.validate(valid_plan, available_agents=["agent1"])
        assert result.passed

    def test_missing_agent_fails(self, engine, valid_plan):
        result = engine.validate(valid_plan, available_agents=["agent2"])
        assert not result.passed

    def test_deadline_warning(self, engine, valid_plan):
        result = engine.validate(valid_plan, deadline=0.1)
        assert result.passed

    def test_resource_limit_warning(self, engine, valid_plan):
        result = engine.validate(valid_plan, resource_limits={"max_cost": 0.5})
        assert result.passed

    def test_constraint_violation_creation(self):
        from app.planning.constraints import ConstraintViolation, ConstraintResult
        r = ConstraintResult()
        r.add("test_rule", "test message", severity="error")
        assert not r.passed
        assert len(r.violations) == 1

    def test_constraint_warning_does_not_fail(self):
        from app.planning.constraints import ConstraintResult
        r = ConstraintResult()
        r.add("warning_rule", "warning only", severity="warning")
        assert r.passed


# =============================================================================
# Simulation Tests
# =============================================================================

class TestSimulation:
    @pytest.fixture
    def sim(self):
        from app.planning.simulation import SimulationEngine
        return SimulationEngine()

    @pytest.fixture
    def plan(self):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p1", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1", estimated_duration=1.0, estimated_cost=1.0))
        plan.add_step(PlanStep(step_id="s2", action_id="a2", dependencies=["s1"], estimated_duration=2.0, estimated_cost=2.0))
        return plan

    def test_simulate_produces_result(self, sim, plan):
        result = sim.simulate(plan)
        assert result.estimated_runtime > 0
        assert result.estimated_resource_usage > 0
        assert result.success_probability > 0
        assert result.success_probability <= 1.0

    def test_empty_plan(self, sim):
        from app.planning.base import Plan
        empty = Plan(plan_id="e", goal_id="g")
        result = sim.simulate(empty)
        assert result.estimated_runtime == 0

    def test_risk_increases_with_steps(self, sim):
        from app.planning.base import Plan, PlanStep
        low = Plan(plan_id="p1", goal_id="g1")
        low.add_step(PlanStep(step_id="s1", action_id="a1"))
        high = Plan(plan_id="p2", goal_id="g1")
        for i in range(20):
            high.add_step(PlanStep(step_id=f"s{i}", action_id="a1"))
        assert sim.simulate(low).risk_score < sim.simulate(high).risk_score

    def test_success_probability_decreases_with_steps(self, sim):
        from app.planning.base import Plan, PlanStep
        low = Plan(plan_id="p1", goal_id="g1")
        low.add_step(PlanStep(step_id="s1", action_id="a1"))
        high = Plan(plan_id="p2", goal_id="g1")
        for i in range(50):
            high.add_step(PlanStep(step_id=f"s{i}", action_id="a1"))
        assert sim.simulate(low).success_probability > sim.simulate(high).success_probability

    def test_bottleneck_identification(self, sim):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p", goal_id="g")
        plan.add_step(PlanStep(step_id="a", action_id="a1", estimated_duration=1.0))
        plan.add_step(PlanStep(step_id="b", action_id="a2", dependencies=["a", "c", "d", "e"], estimated_duration=10.0))
        plan.add_step(PlanStep(step_id="c", action_id="a3", estimated_duration=1.0))
        plan.add_step(PlanStep(step_id="d", action_id="a4", estimated_duration=1.0))
        plan.add_step(PlanStep(step_id="e", action_id="a5", estimated_duration=1.0))
        result = sim.simulate(plan)
        assert len(result.bottlenecks) > 0


# =============================================================================
# Validator Tests
# =============================================================================

class TestValidator:
    @pytest.fixture
    def validator(self):
        from app.planning.validator import PlanValidator
        return PlanValidator()

    @pytest.fixture
    def valid_plan(self):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p1", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1"))
        return plan

    def test_valid_plan(self, validator, valid_plan):
        result = validator.validate(valid_plan)
        assert result.valid

    def test_empty_plan(self, validator):
        from app.planning.base import Plan
        empty = Plan(plan_id="e", goal_id="g")
        result = validator.validate(empty)
        assert not result.valid

    def test_cycle_detection(self, validator):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p", goal_id="g")
        a = PlanStep(step_id="a", action_id="a1", dependencies=["c"])
        b = PlanStep(step_id="b", action_id="a2", dependencies=["a"])
        c = PlanStep(step_id="c", action_id="a3", dependencies=["b"])
        plan.add_step(a)
        plan.add_step(b)
        plan.add_step(c)
        result = validator.validate(plan)
        assert not result.valid

    def test_missing_dependency(self, validator):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p", goal_id="g")
        plan.add_step(PlanStep(step_id="a", action_id="a1", dependencies=["nonexistent"]))
        result = validator.validate(plan)
        assert not result.valid

    def test_deadlock_detection(self, validator):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p", goal_id="g")
        a = PlanStep(step_id="a", action_id="a1", dependencies=["b"], fallback_step_id="b")
        b = PlanStep(step_id="b", action_id="a2", dependencies=["a"], fallback_step_id="a")
        plan.add_step(a)
        plan.add_step(b)
        result = validator.validate(plan)
        assert not result.valid

    def test_resource_conflict_warning(self, validator):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="p", goal_id="g")
        a = PlanStep(step_id="a", action_id="a1", agent_id="agent1")
        b = PlanStep(step_id="b", action_id="a2", agent_id="agent1")
        c = PlanStep(step_id="c", action_id="a3", dependencies=["a", "b"])
        plan.add_step(a)
        plan.add_step(b)
        plan.add_step(c)
        result = validator.validate(plan)
        assert result.valid


# =============================================================================
# Plan Memory Tests
# =============================================================================

class TestPlanMemory:
    @pytest.fixture
    def memory(self):
        from app.planning.memory import PlanMemory
        tmpdir = tempfile.mkdtemp()
        mem = PlanMemory(base_path=tmpdir)
        yield mem
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def sample_plan(self):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="test-plan", goal_id="goal-1", goal_name="test goal")
        plan.add_step(PlanStep(step_id="s1", action_id="a1"))
        plan.add_step(PlanStep(step_id="s2", action_id="a2", dependencies=["s1"]))
        return plan

    @pytest.mark.anyio
    async def test_save_and_load(self, memory, sample_plan):
        await memory.save_plan(sample_plan)
        loaded = await memory.load_plan("test-plan")
        assert loaded is not None
        assert loaded.plan_id == "test-plan"
        assert loaded.goal_name == "test goal"
        assert len(loaded.steps) == 2

    @pytest.mark.anyio
    async def test_cache_hit(self, memory, sample_plan):
        memory.cache_plan(sample_plan)
        loaded = await memory.load_plan("test-plan")
        assert loaded is not None
        stats = memory.get_statistics()
        assert stats["cache_hits"] > 0

    @pytest.mark.anyio
    async def test_cache_miss(self, memory):
        loaded = await memory.load_plan("non-existent")
        assert loaded is None

    @pytest.mark.anyio
    async def test_find_similar_by_name(self, memory, sample_plan):
        await memory.save_plan(sample_plan)
        results = await memory.find_similar("test goal")
        assert len(results) >= 1

    @pytest.mark.anyio
    async def test_template_storage(self, memory, sample_plan):
        await memory.store_template("template-1", sample_plan)
        loaded = await memory.load_template("template-1")
        assert loaded is not None
        assert loaded.plan_id == "test-plan"

    @pytest.mark.anyio
    async def test_template_not_found(self, memory):
        loaded = await memory.load_template("non-existent")
        assert loaded is None

    @pytest.mark.anyio
    async def test_archive(self, memory, sample_plan):
        await memory.save_plan(sample_plan)
        archived = await memory.archive_plan("test-plan")
        assert archived

    @pytest.mark.anyio
    async def test_archive_nonexistent(self, memory):
        archived = await memory.archive_plan("non-existent")
        assert not archived

    @pytest.mark.anyio
    async def test_clear(self, memory, sample_plan):
        await memory.save_plan(sample_plan)
        assert len(memory.get_statistics()) > 0
        await memory.clear()
        loaded = await memory.load_plan("test-plan")
        assert loaded is None

    def test_statistics(self, memory):
        stats = memory.get_statistics()
        assert "total_saved" in stats
        assert "cache_hits" in stats


# =============================================================================
# Planner Tests
# =============================================================================

class TestPlanningEngine:
    @pytest.fixture
    def engine(self):
        from app.planning.planner import PlanningEngine
        return PlanningEngine()

    def test_create_goal(self, engine):
        goal = engine.create_goal("Build project", "Build the main project",
                                  priority=8.0)
        assert goal.goal_id is not None
        assert goal.name == "Build project"
        assert goal.priority == 8.0
        assert goal.status == "active"
        assert engine.get_goal(goal.goal_id) is goal

    def test_decompose_goal(self, engine):
        from app.planning.goal import Goal
        parent = engine.create_goal("Parent")
        sub_goals = engine.decompose_goal(parent)
        assert len(sub_goals) >= 1
        for sub in sub_goals:
            assert sub.parent_goal_id == parent.goal_id

    def test_decompose_with_capabilities(self, engine):
        from app.planning.goal import Goal
        goal = engine.create_goal("Dev task",
                                  required_capabilities=["code_generation", "testing"])
        sub_goals = engine.decompose_goal(goal)
        assert len(sub_goals) >= 2

    @pytest.mark.anyio
    async def test_generate_plan(self, engine):
        goal = engine.create_goal("Simple task")
        plan = await engine.generate_plan(goal)
        assert plan is not None
        assert plan.goal_id == goal.goal_id
        assert len(plan.steps) >= 1
        assert plan.status == "generated"

    @pytest.mark.anyio
    async def test_generate_plan_with_capabilities(self, engine):
        from app.planning.goal import Goal
        goal = engine.create_goal("Research and code",
                                  required_capabilities=["web_search", "code_generation"])
        plan = await engine.generate_plan(goal)
        assert plan is not None
        assert len(plan.steps) >= 1

    @pytest.mark.anyio
    async def test_validate_plan(self, engine):
        from app.planning.base import Plan, PlanStep
        goal = engine.create_goal("Validate test")
        plan = await engine.generate_plan(goal)
        result = await engine.validate_plan(plan)
        assert isinstance(result.valid, bool)

    @pytest.mark.anyio
    async def test_validate_plan_with_cycle(self, engine):
        from app.planning.base import Plan, PlanStep
        goal = engine.create_goal("Cycle test")
        plan = await engine.generate_plan(goal)
        plan.steps[0].dependencies.append(plan.steps[0].step_id)
        result = await engine.validate_plan(plan)
        assert not result.valid

    def test_simulate_plan(self, engine):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="sim", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1", estimated_duration=2.0))
        result = engine.simulate_plan(plan)
        assert result.estimated_runtime > 0

    def test_score_plan(self, engine):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="score", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1"))
        scores = engine.score_plan(plan)
        assert scores.total > 0

    @pytest.mark.anyio
    async def test_optimize_plan(self, engine):
        goal = engine.create_goal("Optimize test")
        plan = await engine.generate_plan(goal)
        before = plan.total_cost
        optimized = await engine.optimize_plan(plan)
        assert optimized.total_cost <= before
        assert optimized.version > 1

    @pytest.mark.anyio
    async def test_revise_plan(self, engine):
        from app.planning.base import Plan, PlanStep
        goal = engine.create_goal("Revise test")
        plan = await engine.generate_plan(goal)
        revised = await engine.revise_plan(plan, {
            "remove_steps": [],
            "add_steps": [
                {"action_id": "test", "estimated_cost": 2.0, "estimated_duration": 2.0},
            ],
        })
        assert revised is not None
        assert revised.version > plan.version

    @pytest.mark.anyio
    async def test_find_similar_plans(self, engine):
        goal = engine.create_goal("Similar task")
        plan = await engine.generate_plan(goal)
        similar = await engine.find_similar_plans(goal)
        assert isinstance(similar, list)

    @pytest.mark.anyio
    async def test_template_roundtrip(self, engine):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="tpl", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1"))
        await engine.store_template("my-template", plan)
        loaded = await engine.load_template("my-template")
        assert loaded is not None
        assert loaded.plan_id == "tpl"

    @pytest.mark.anyio
    async def test_archive_plan(self, engine):
        goal = engine.create_goal("Archive test")
        plan = await engine.generate_plan(goal)
        archived = await engine.archive_plan(plan.plan_id)
        assert archived

    @pytest.mark.anyio
    async def test_archive_nonexistent(self, engine):
        archived = await engine.archive_plan("non-existent")
        assert not archived

    def test_update_goal_status(self, engine):
        goal = engine.create_goal("Status test")
        assert engine.update_goal_status(goal.goal_id, "in_progress")
        assert engine.get_goal(goal.goal_id).status == "in_progress"
        assert not engine.update_goal_status("non-existent", "done")

    def test_health(self, engine):
        h = engine.health()
        assert h.status == "healthy"
        assert h.total_goals == 0

    @pytest.mark.anyio
    async def test_health_after_plan(self, engine):
        engine.create_goal("Health test")
        h = engine.health()
        assert h.total_goals >= 1

    def test_register_action(self, engine):
        from app.planning.action import Action
        a = Action("custom", "Custom Action")
        engine.register_action(a)
        assert "custom" in engine._actions

    @pytest.mark.anyio
    async def test_check_constraints(self, engine):
        from app.planning.base import Plan, PlanStep
        plan = Plan(plan_id="cc", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1"))
        goal = engine.create_goal("Constraint check")
        result = await engine.check_constraints(goal, plan)
        assert isinstance(result.passed, bool)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    @pytest.mark.anyio
    async def test_full_planning_lifecycle(self):
        from app.planning.planner import PlanningEngine
        engine = PlanningEngine()

        goal = engine.create_goal("Integration test",
                                  description="Full lifecycle test",
                                  priority=7.5,
                                  required_capabilities=["research", "code"])
        assert goal is not None

        plan = await engine.generate_plan(goal)
        assert plan is not None
        assert len(plan.steps) >= 1

        sim = engine.simulate_plan(plan)
        assert sim.estimated_runtime > 0
        assert sim.success_probability > 0

        result = await engine.validate_plan(plan)
        assert isinstance(result.valid, bool)

        scores = engine.score_plan(plan)
        assert scores.total > 0

        optimized = await engine.optimize_plan(plan)
        assert optimized.total_cost <= plan.total_cost

        revised = await engine.revise_plan(optimized, {
            "add_steps": [{"action_id": "test", "estimated_cost": 1.0, "estimated_duration": 1.0}],
        })
        assert revised.step_count >= optimized.step_count

        similar = await engine.find_similar_plans(goal)
        assert isinstance(similar, list)

        h = engine.health()
        assert h.status == "healthy"
        assert h.plans_generated >= 1

    @pytest.mark.anyio
    async def test_goal_hierarchy(self):
        from app.planning.planner import PlanningEngine
        engine = PlanningEngine()

        parent = engine.create_goal("Mission")
        children = engine.decompose_goal(parent)
        assert len(children) >= 1

        for child in children:
            assert child.parent_goal_id == parent.goal_id
            assert child.goal_id in parent.child_goal_ids

    @pytest.mark.anyio
    async def test_plan_persistence(self):
        import tempfile, shutil
        from app.planning.planner import PlanningEngine

        tmpdir = tempfile.mkdtemp()
        try:
            engine = PlanningEngine(memory_base_path=tmpdir)
            goal = engine.create_goal("Persist test")
            plan = await engine.generate_plan(goal)

            loaded = await engine._memory.load_plan(plan.plan_id)
            assert loaded is not None

            stats = engine.memory_stats()
            assert stats["total_saved"] >= 1

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_event_types_exist(self):
        from app.planning.events import (
            GoalCreated, GoalUpdated, PlanGenerated, PlanValidated,
            PlanRejected, PlanOptimized, PlanExecuted, PlanArchived,
        )
        e1 = GoalCreated("g1", "test", 5.0)
        assert e1.topic == "GoalCreated"
        e2 = PlanGenerated("p1", "g1", 3)
        assert e2.topic == "PlanGenerated"
        e3 = PlanOptimized("p1", 0.5, 0.8)
        assert e3.topic == "PlanOptimized"
        e4 = PlanRejected("p1", "cycle detected")
        assert e4.topic == "PlanRejected"
        e5 = PlanArchived("p1", "test")
        assert e5.topic == "PlanArchived"
        e6 = PlanExecuted("p1", "g1", True)
        assert e6.topic == "PlanExecuted"

    def test_health_model(self):
        from app.planning.health import PlanningHealth
        h = PlanningHealth(
            plans_generated=10,
            average_planning_time_ms=50.0,
            validation_failures=2,
            cache_hits=15,
            total_goals=5,
            active_goals=3,
        )
        assert h.plans_generated == 10
        assert h.validation_failures == 2
        d = h.to_dict()
        assert d["status"] == "healthy"
        assert d["total_goals"] == 5

    def test_module_exports(self):
        from app.planning import (
            Plan, PlanStep, Goal, Action, ActionGraph, PlanningEngine,
            ConstraintEngine, HeuristicScorer, SimulationEngine,
            PlanValidator, PlanMemory, PlanningHealth,
        )
        assert PlanningEngine is not None
        assert Goal is not None
        assert ActionGraph is not None
        assert PlanMemory is not None

    @pytest.mark.anyio
    async def test_plan_execute_without_agent_manager(self):
        from app.planning.planner import PlanningEngine
        from app.planning.base import Plan, PlanStep
        engine = PlanningEngine()
        plan = Plan(plan_id="exec", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1"))
        success = await engine.execute_plan(plan)
        assert not success

    @pytest.mark.anyio
    async def test_constraint_integration(self):
        from app.planning.planner import PlanningEngine
        from app.planning.base import Plan, PlanStep
        engine = PlanningEngine()
        plan = Plan(plan_id="ci", goal_id="g1")
        plan.add_step(PlanStep(step_id="s1", action_id="a1", agent_id="missing-agent"))
        goal = engine.create_goal("Constraint integration")
        result = await engine.check_constraints(goal, plan)
        assert result.passed
