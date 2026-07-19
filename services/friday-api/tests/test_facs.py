import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, AsyncMock

from scripts.ai_session_manager import AISessionManager
from app.facs.subscriber import FACSSubscriber
from app.autonomous_dev.events import (
    AutonomousGoalCreated,
    AutonomousGoalStatusChanged,
    AutonomousTaskStatusChanged,
    AutonomousReflectionGenerated
)

@pytest.fixture
def temp_repo():
    # Setup temporary repository root
    temp_dir = tempfile.mkdtemp()
    docs_dir = os.path.join(temp_dir, "docs")
    os.makedirs(docs_dir)
    
    # Create mock documentation files
    mock_files = {
        "PROJECT_STATE.md": """# Project State
- **Current Version**: v1.5.0-rc1
- **Current Branch**: main
- **Last Updated**: 2026-07-19T00:00:00Z
""",
        "AI_HANDOFF.md": """# AI Handoff Log
""",
        "CURRENT_SPRINT.md": """# Current Sprint
## Tasks Checklist
- [ ] Phase 6 - Validation
""",
        "CHANGELOG.md": """# Changelog
## [1.5.0-rc1]
"""
    }
    
    for name, content in mock_files.items():
        with open(os.path.join(docs_dir, name), "w") as f:
            f.write(content)
            
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.mark.anyio
async def test_session_manager_start_and_end(temp_repo):
    manager = AISessionManager(root_dir=temp_repo)
    
    # Test start session (should run with no errors)
    manager.start_session()
    
    # Test end session
    manager.end_session(
        model_name="TestModel",
        duration="30 mins",
        tasks_completed=["Implemented tests", "Fixed bugs"],
        notes="All green."
    )
    
    # Verify state was updated
    with open(manager.paths["state"], "r") as f:
        state_content = f.read()
        assert "- **Last Updated**:" in state_content
        assert "2026-07-19T00:00:00Z" not in state_content
        
    # Verify handoff was appended
    with open(manager.paths["handoff"], "r") as f:
        handoff_content = f.read()
        assert "### Session: TestModel" in handoff_content
        assert "Implemented tests" in handoff_content
        assert "All green." in handoff_content

@pytest.mark.anyio
async def test_facs_subscriber_events(temp_repo):
    # Setup mock event bus
    mock_bus = MagicMock()
    mock_bus.subscribe = MagicMock()
    
    subscriber = FACSSubscriber(event_bus=mock_bus)
    subscriber.docs_dir = os.path.join(temp_repo, "docs")
    
    # Test initialize
    await subscriber.initialize()
    assert mock_bus.subscribe.called
    assert mock_bus.subscribe.call_count == 4
    
    # Test on_goal_created callback
    goal_created = AutonomousGoalCreated(goal_id="g123", prompt="Run validations")
    subscriber.on_goal_created(goal_created)
    
    # Verify PROJECT_STATE.md got the active session block
    with open(os.path.join(subscriber.docs_dir, "PROJECT_STATE.md"), "r") as f:
        state_content = f.read()
        assert "### Active Autonomous Session" in state_content
        assert "Goal ID**: g123" in state_content
        assert "Session Status**: active" in state_content
        
    # Verify CURRENT_SPRINT.md got the task dynamically added
    with open(os.path.join(subscriber.docs_dir, "CURRENT_SPRINT.md"), "r") as f:
        sprint_content = f.read()
        assert "Autonomous Goal: Run validations" in sprint_content
        assert "[/]" in sprint_content

    # Test on_goal_status completed callback
    goal_completed = AutonomousGoalStatusChanged(goal_id="g123", status="completed")
    subscriber.on_goal_status(goal_completed)
    
    with open(os.path.join(subscriber.docs_dir, "PROJECT_STATE.md"), "r") as f:
        state_content = f.read()
        assert "Session Status**: completed" in state_content

    # Test on_task_status completed callback
    task_completed = AutonomousTaskStatusChanged(task_id="t999", status="completed")
    subscriber.on_task_status(task_completed)
    
    with open(os.path.join(subscriber.docs_dir, "CURRENT_SPRINT.md"), "r") as f:
        sprint_content = f.read()
        assert "t999" in sprint_content
        assert "[x]" in sprint_content

    # Test reflection generated callback
    reflection_event = AutonomousReflectionGenerated(
        goal_id="g123",
        task_id="t999",
        reflection={
            "summary": "Everything succeeded.",
            "learnings": ["Test passes verified", "EventBus is stable"]
        }
    )
    subscriber.on_reflection_generated(reflection_event)
    
    with open(os.path.join(subscriber.docs_dir, "AI_HANDOFF.md"), "r") as f:
        handoff_content = f.read()
        assert "Automated Reflection (Task: t999)" in handoff_content
        assert "Everything succeeded." in handoff_content
        assert "Test passes verified" in handoff_content
