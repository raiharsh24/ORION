import pytest
from app.autonomous_dev.planner import AutonomousPlanner
from app.autonomous_dev.models import AutonomousGoal, AutonomousTask

@pytest.mark.anyio
async def test_planner_creates_inspect_plan():
    """
    Tests that the planner creates the correct task for an 'inspect' goal.
    """
    planner = AutonomousPlanner()
    goal = AutonomousGoal(id="test-goal-1", prompt="inspect the codebase")

    new_tasks = await planner.create_plan(goal, existing_tasks=[])

    assert len(new_tasks) == 1
    task = new_tasks[0]
    assert isinstance(task, AutonomousTask)
    assert task.goal_id == "test-goal-1"
    assert task.description == "Inspect and analyze the current workspace."
    assert not task.dependencies

@pytest.mark.anyio
async def test_planner_does_not_duplicate_tasks():
    """
    Tests that the planner does not create a new task if one already exists.
    """
    planner = AutonomousPlanner()
    goal = AutonomousGoal(id="test-goal-2", prompt="inspect the codebase")
    existing_task = AutonomousTask(
        id="existing-task",
        goal_id="test-goal-2",
        description="Inspect and analyze the current workspace."
    )

    new_tasks = await planner.create_plan(goal, existing_tasks=[existing_task])

    assert len(new_tasks) == 0

@pytest.mark.anyio
async def test_planner_handles_unknown_goal():
    """
    Tests that the planner returns an empty list for an unknown goal prompt.
    """
    planner = AutonomousPlanner()
    goal = AutonomousGoal(id="test-goal-3", prompt="do something unknown")

    new_tasks = await planner.create_plan(goal, existing_tasks=[])

    assert len(new_tasks) == 0
