import pytest
from datetime import datetime, timezone
from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RuntimeStepStatus, RuntimeWorkflowStatus,
    ScheduleConfig, RetryPolicy, ExecutionPlanInput, WorkflowSummary
)
from datetime import datetime, timezone


def test_runtime_step_defaults():
    step = RuntimeStep(step_id="s1", name="Step 1", step_type="tool")
    assert step.step_id == "s1"
    assert step.name == "Step 1"
    assert step.step_type == "tool"
    assert step.status == RuntimeStepStatus.PENDING
    assert step.input == {}
    assert step.depends_on == []
    assert step.retry_policy.max_retries == 0
    assert step.timeout is None
    assert step.parallel_group is None
    assert step.retry_count == 0


def test_runtime_workflow_defaults():
    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    assert wf.workflow_id == "wf-1"
    assert wf.name == "Test"
    assert wf.status == RuntimeWorkflowStatus.PENDING
    assert wf.steps == {}
    assert wf.variables == {}
    assert wf.metadata == {}
    assert wf.created_at is not None
    assert wf.error is None


def test_runtime_workflow_has_pending_steps():
    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    assert wf.has_pending_steps() is False

    s1 = RuntimeStep(step_id="s1", name="S1", step_type="tool")
    wf.steps["s1"] = s1
    assert wf.has_pending_steps() is True

    s1.status = RuntimeStepStatus.COMPLETED
    assert wf.has_pending_steps() is False

    s2 = RuntimeStep(step_id="s2", name="S2", step_type="tool",
                     depends_on=["s1"])
    wf.steps["s2"] = s2
    assert wf.has_pending_steps() is True
    assert wf.has_pending_steps() is True


def test_runtime_workflow_is_terminal():
    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    assert wf.is_terminal() is False
    wf.status = RuntimeWorkflowStatus.COMPLETED
    assert wf.is_terminal() is True
    wf.status = RuntimeWorkflowStatus.FAILED
    assert wf.is_terminal() is True
    wf.status = RuntimeWorkflowStatus.CANCELLED
    assert wf.is_terminal() is True


def test_runtime_workflow_get_parallel_groups():
    wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
    s1 = RuntimeStep(step_id="s1", name="S1", step_type="tool",
                     parallel_group="g1")
    s2 = RuntimeStep(step_id="s2", name="S2", step_type="tool",
                     parallel_group="g1")
    s3 = RuntimeStep(step_id="s3", name="S3", step_type="tool")
    wf.steps = {"s1": s1, "s2": s2, "s3": s3}
    groups = wf.get_parallel_groups()
    assert "g1" in groups
    assert "s3" in groups
    assert len(groups["g1"]) == 2
    assert len(groups["s3"]) == 1


def test_schedule_config():
    cfg = ScheduleConfig(schedule_type="CRON", cron_expression="*/5 * * * *")
    assert cfg.schedule_type.value == "CRON"
    assert cfg.cron_expression == "*/5 * * * *"

    cfg2 = ScheduleConfig()
    assert cfg2.schedule_type.value == "ONCE"
    assert cfg2.cron_expression is None


def test_retry_policy():
    rp = RetryPolicy(max_retries=3, base_delay=2.0)
    assert rp.max_retries == 3
    assert rp.base_delay == 2.0

    rp2 = RetryPolicy()
    assert rp2.max_retries == 0
    assert rp2.base_delay == 1.0


def test_execution_plan_input():
    plan = ExecutionPlanInput(
        plan_id="plan-1",
        goal="Test goal",
        steps=[
            {"step_id": "s1", "name": "S1", "type": "tool", "input": {"cmd": "echo"}}
        ],
        variables={"var1": "val1"},
        metadata={"source": "test"}
    )
    assert plan.plan_id == "plan-1"
    assert len(plan.steps) == 1
    assert plan.steps[0]["step_id"] == "s1"


def test_workflow_summary():
    now = datetime.now(timezone.utc)
    summary = WorkflowSummary(
        workflow_id="wf-1",
        name="Test",
        status="RUNNING",
        total_steps=10,
        completed_steps=4,
        failed_steps=1,
        created_at=now,
        updated_at=now,
    )
    assert summary.workflow_id == "wf-1"
    assert summary.status == "RUNNING"
    assert summary.total_steps == 10
    assert summary.completed_steps == 4
