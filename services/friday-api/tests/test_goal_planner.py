import pytest

from app.friday.planner_schema import ExecutionPlan
from app.intent.types import IntentType
from app.goal_planner import GoalPlanner, GoalPlan, GoalTask


class TestGoalPlanModels:
    def test_empty_goal_plan(self):
        gp = GoalPlan(goal="test")
        assert gp.task_count == 0
        assert gp.capabilities == []
        assert gp.parallel_groups == []

    def test_goal_plan_with_tasks(self):
        gp = GoalPlan(goal="test", tasks=[
            GoalTask(id="t1", title="read", description="Read file",
                     required_capability="filesystem"),
            GoalTask(id="t2", title="write", description="Write file",
                     required_capability="filesystem",
                     dependencies=["t1"]),
        ])
        assert gp.task_count == 2
        assert gp.capabilities == ["filesystem"]

    def test_goal_plan_capabilities_dedup(self):
        gp = GoalPlan(goal="test", tasks=[
            GoalTask(id="t1", title="read", description="Read",
                     required_capability="filesystem"),
            GoalTask(id="t2", title="browse", description="Browse",
                     required_capability="browser"),
            GoalTask(id="t3", title="write", description="Write",
                     required_capability="filesystem"),
        ])
        assert gp.capabilities == ["filesystem", "browser"]

    def test_parallel_groups(self):
        gp = GoalPlan(goal="test", tasks=[
            GoalTask(id="t1", title="a", description="", required_capability="fs",
                     parallel_group="g1"),
            GoalTask(id="t2", title="b", description="", required_capability="fs",
                     parallel_group="g1"),
            GoalTask(id="t3", title="c", description="", required_capability="br"),
        ])
        assert "g1" in gp.parallel_groups


class TestGoalPlannerConversation:
    def test_conversation_intent_returns_no_tasks(self):
        planner = GoalPlanner()
        gp = planner.create_goal_plan(
            prompt="Hello",
            intent=IntentType.CONVERSATION,
        )
        assert gp.task_count == 0

    def test_unknown_intent_returns_no_tasks(self):
        planner = GoalPlanner()
        gp = planner.create_goal_plan(
            prompt="test",
            intent=IntentType.UNKNOWN,
        )
        assert gp.task_count == 0


class TestGoalPlannerSingleStep:
    def test_browser_intent_creates_task(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="browser", goal="Go to example.com",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["browser"],
        )
        gp = planner.create_goal_plan(
            prompt="Go to example.com",
            intent=IntentType.BROWSER,
            plan=plan,
        )
        assert gp.task_count >= 1
        tasks = gp.tasks
        caps = {t.required_capability for t in tasks}
        assert "browser" in caps

    def test_filesystem_intent_creates_task(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="filesystem", goal="Read file",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["filesystem"],
        )
        gp = planner.create_goal_plan(
            prompt="Read /etc/hosts",
            intent=IntentType.CODING,
            plan=plan,
        )
        assert gp.task_count >= 1
        assert any(t.required_capability == "filesystem" for t in gp.tasks)


class TestGoalPlannerMultiStep:
    def test_plan_with_two_steps(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="filesystem", goal="Search and read",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["filesystem"],
            steps=[
                {"step": 1, "action": "filesystem_op", "args": {"op": "search"}},
                {"step": 2, "action": "filesystem_op", "args": {"op": "read"}},
            ],
        )
        gp = planner.create_goal_plan(
            prompt="Search and read file",
            intent=IntentType.CODING,
            plan=plan,
        )
        assert gp.task_count == 2
        assert gp.tasks[0].dependencies == []
        assert gp.tasks[1].dependencies == [gp.tasks[0].id]

    def test_plan_with_three_steps_chain(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="filesystem", goal="Search, read, write",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["filesystem"],
            steps=[
                {"step": 1, "action": "filesystem_op", "args": {"op": "search"}},
                {"step": 2, "action": "filesystem_op", "args": {"op": "read"}},
                {"step": 3, "action": "filesystem_op", "args": {"op": "write"}},
            ],
        )
        gp = planner.create_goal_plan(
            prompt="Search, read, write",
            intent=IntentType.CODING,
            plan=plan,
        )
        assert gp.task_count == 3
        for i in range(1, 3):
            assert gp.tasks[i].dependencies == [gp.tasks[i - 1].id]

    def test_plan_no_steps_falls_back_to_single(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="terminal", goal="Run command",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["terminal"],
        )
        gp = planner.create_goal_plan(
            prompt="Run ls -la",
            intent=IntentType.TERMINAL,
            plan=plan,
        )
        assert gp.task_count == 1
        assert gp.tasks[0].required_capability == "terminal"


class TestGoalPlannerDependencies:
    def test_step_capability_from_op(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="filesystem", goal="Read file",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["filesystem"],
            steps=[
                {"step": 1, "action": "filesystem_op", "args": {"op": "read"}},
            ],
        )
        gp = planner.create_goal_plan(
            prompt="Read file",
            intent=IntentType.CODING,
            plan=plan,
        )
        assert gp.tasks[0].required_capability == "filesystem"
        assert "read" in gp.tasks[0].title or "file" in gp.tasks[0].title


class TestGoalPlannerEdgeCases:
    def test_empty_plan(self):
        planner = GoalPlanner()
        gp = planner.create_goal_plan(
            prompt="test",
            intent=IntentType.DESKTOP,
            plan=None,
        )
        assert gp.task_count == 1
        assert gp.tasks[0].required_capability == "desktop"

    def test_plan_without_capabilities(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="desktop", goal="Click button",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False,
        )
        gp = planner.create_goal_plan(
            prompt="Click the button",
            intent=IntentType.DESKTOP,
            plan=plan,
        )
        assert gp.task_count >= 1

    def test_resolve_step_from_action(self):
        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="terminal", goal="Run shell command",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False,
            steps=[
                {"step": 1, "action": "terminal_exec", "args": {}},
            ],
        )
        gp = planner.create_goal_plan(
            prompt="Run command",
            intent=IntentType.TERMINAL,
            plan=plan,
        )
        assert gp.task_count == 1
        assert gp.tasks[0].required_capability == "terminal"


class TestGoalPlanLogging:
    def test_create_goal_plan_logs(self, capsys):
        import io
        from loguru import logger
        logger.remove()
        logger.add(lambda msg: None, format="{message}")

        planner = GoalPlanner()
        plan = ExecutionPlan(
            intent="browser", goal="Search web",
            toolRequired=True, memoryRequired=False,
            clarificationRequired=False, capabilities=["browser"],
            steps=[
                {"step": 1, "action": "web_search", "args": {"query": "test"}},
            ],
        )
        gp = planner.create_goal_plan(
            prompt="Search for test",
            intent=IntentType.BROWSER,
            plan=plan,
        )
        assert gp.task_count == 1
        assert gp.tasks[0].required_capability in ("browser", "search")


class TestGoalPlannerStreaming:
    @pytest.mark.anyio
    async def test_goal_planner_in_execution_context(self):
        """Verify GoalPlan can be created and attached to an execution context."""
        from app.execution.context import ExecutionContext
        ctx = ExecutionContext(prompt="test")
        planner = GoalPlanner()
        gp = planner.create_goal_plan(
            prompt="test",
            intent=IntentType.DESKTOP,
            plan=None,
        )
        ctx.goal_plan = gp
        assert ctx.goal_plan is not None
        assert ctx.goal_plan.task_count >= 1
