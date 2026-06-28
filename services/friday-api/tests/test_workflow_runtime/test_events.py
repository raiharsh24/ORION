import pytest
from datetime import datetime
from app.workflow_runtime.events import (
    WorkflowStarted, WorkflowPaused, WorkflowResumed,
    WorkflowStepStarted, WorkflowStepCompleted,
    WorkflowFailed, WorkflowCompleted, WorkflowCancelled
)
from app.events.events import FridayEvent


def test_workflow_started():
    event = WorkflowStarted("wf-1", "Test", 5)
    assert isinstance(event, FridayEvent)
    assert event.workflow_id == "wf-1"
    assert event.workflow_name == "Test"
    assert event.total_steps == 5
    assert event.topic == "WorkflowStarted"


def test_workflow_paused():
    event = WorkflowPaused("wf-1")
    assert event.workflow_id == "wf-1"
    assert event.topic == "WorkflowPaused"


def test_workflow_resumed():
    event = WorkflowResumed("wf-1")
    assert event.workflow_id == "wf-1"
    assert event.topic == "WorkflowResumed"


def test_workflow_step_started():
    event = WorkflowStepStarted("wf-1", "s1", "Step 1", "tool")
    assert event.workflow_id == "wf-1"
    assert event.step_id == "s1"
    assert event.step_name == "Step 1"
    assert event.step_type == "tool"
    assert event.topic == "WorkflowStepStarted"


def test_workflow_step_completed():
    event = WorkflowStepCompleted("wf-1", "s1", success=True)
    assert event.workflow_id == "wf-1"
    assert event.step_id == "s1"
    assert event.success is True
    assert event.topic == "WorkflowStepCompleted"

    event2 = WorkflowStepCompleted("wf-1", "s2", success=False)
    assert event2.success is False


def test_workflow_failed():
    event = WorkflowFailed("wf-1", "Something went wrong")
    assert event.workflow_id == "wf-1"
    assert event.error == "Something went wrong"
    assert event.topic == "WorkflowFailed"


def test_workflow_completed():
    event = WorkflowCompleted("wf-1", 10, 2)
    assert event.workflow_id == "wf-1"
    assert event.total_steps == 10
    assert event.failed_steps == 2
    assert event.topic == "WorkflowCompleted"


def test_workflow_cancelled():
    event = WorkflowCancelled("wf-1")
    assert event.workflow_id == "wf-1"
    assert event.topic == "WorkflowCancelled"
