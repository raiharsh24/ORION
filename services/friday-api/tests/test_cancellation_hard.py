import pytest
import asyncio
import subprocess
import time
from app.kernel import FridayKernel, FridayKernelConfig
from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RetryPolicy, RuntimeWorkflowStatus
)

def find_sleep_processes():
    try:
        output = subprocess.check_output(["pgrep", "-f", "sleep 10"]).decode().strip()
        return [int(pid) for pid in output.split() if pid]
    except subprocess.CalledProcessError:
        return []

@pytest.mark.anyio
async def test_hard_cancellation_kills_subprocess():
    # 1. Clean kernel state and boot
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance(FridayKernelConfig())
    await kernel.boot()

    # 2. Verify pgrep baseline
    initial_sleeps = find_sleep_processes()
    for pid in initial_sleeps:
        try:
            import os
            import signal
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    # 3. Create workflow that spawns a sleep subprocess
    workflow_runtime = kernel.get_service("workflow_runtime_manager")
    assert workflow_runtime is not None

    wf = RuntimeWorkflow(
        workflow_id="hard-cancel-test-wf",
        name="Hard Cancellation Test",
    )
    s1 = RuntimeStep(
        step_id="s1",
        name="Spawn Subprocess",
        step_type="tool",
        input={"tool_name": "terminal", "args": {"cmd": "sleep 10"}},
        retry_policy=RetryPolicy(max_retries=0),
    )
    wf.steps = {"s1": s1}

    # 4. Start workflow execution
    await workflow_runtime.start_from_workflow(wf)
    
    # Wait for the subprocess to be spawned
    await asyncio.sleep(1.0)

    # 5. Assert subprocess is active in the system
    stored_wf = await workflow_runtime.get_stored("hard-cancel-test-wf")
    print("WORKFLOW STATUS DURING TEST:", stored_wf.status)
    print("STEP RESULT:", stored_wf.steps["s1"].result)
    print("STEP ERROR:", stored_wf.steps["s1"].error)
    active_sleeps = find_sleep_processes()
    assert len(active_sleeps) >= 1, f"Subprocess 'sleep 10' was not found running in the system. Step status: {stored_wf.steps['s1'].status}"

    # 6. Cancel the workflow
    cancelled = await workflow_runtime.cancel("hard-cancel-test-wf")
    assert cancelled is True

    # Allow time for cancellation cleanup and signal propagation
    await asyncio.sleep(1.0)

    # 7. Assert subprocess has been terminated
    remaining_sleeps = find_sleep_processes()
    assert len(remaining_sleeps) == 0, f"Leaked subprocesses detected: {remaining_sleeps}"

    # 8. Assert workflow state is set to CANCELLED in persistence
    stored = await workflow_runtime.get_stored("hard-cancel-test-wf")
    assert stored is not None
    assert stored.status == RuntimeWorkflowStatus.CANCELLED

    # 9. Clean shutdown
    await kernel.shutdown()
