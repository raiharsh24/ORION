# Mission Execution Engine Walkthrough

## Overview

The Mission Execution Engine manages long-running tasks composed of one or more
workflows. It provides pause/resume, checkpoint recovery, workflow chaining,
background execution, and cancellation — all while preserving execution state
for restart resilience.

## Architecture Layers

```
MissionExecutor
  └─ MissionPlanner          (workflow ordering)
  └─ MissionStore            (mission CRUD)
  └─ CheckpointManager       (pause/resume state)
  └─ WorkflowExecutor         (Phase 6 Sprint 4)
       └─ ToolExecutionEngine (Phase 6 Sprint 3)
            └─ ToolSelectionEngine (Phase 6 Sprint 2)
                 └─ ToolRegistry (Phase 6 Sprint 1)
```

The MissionExecutor never bypasses these layers. All tool execution is
delegated through WorkflowExecutor → ToolExecutionEngine.

## Mission Lifecycle

```
  ┌──────────┐
  │  PENDING │  create_mission()
  └────┬─────┘
       │ start_mission()
       v
  ┌──────────┐
  │  RUNNING │ ─── pause_mission() ──→ ┌───────┐
  └────┬─────┘                          │ PAUSED│
       │                                └───┬───┘
       │                                    │ resume_mission()
       ├────────────────────────────────────┘
       v
  ┌───────────┐
  │ COMPLETED │  (all workflows succeed)
  ├───────────┤
  │  FAILED   │  (any workflow fails)
  ├───────────┤
  │ CANCELLED │  cancel_mission()
  └───────────┘
```

## Quick Start

```python
from app.mission_engine.executor import MissionExecutor
from app.mission_engine.mission import MissionStore
from app.mission_engine.checkpoint import CheckpointManager
from app.mission_engine.planner import MissionPlanner

executor = MissionExecutor(
    workflow_executor=workflow_executor,
    store=MissionStore(),
    checkpoint_manager=CheckpointManager(),
    planner=MissionPlanner(store),
    event_bus=event_bus,
)

# Create a mission with two workflows
wf1 = WorkflowGraphBuilder.build([WorkflowNode(id="a", tool_id="tool_a")], [])
wf2 = WorkflowGraphBuilder.build([WorkflowNode(id="b", tool_id="tool_b")], [])

mission = executor.create_mission(
    name="Data Pipeline",
    workflow_graphs={"extract": wf1, "transform": wf2},
)

# Execute synchronously
result = await executor.start_mission(mission.id)
assert result.status == MissionState.COMPLETED
```

## Background Execution

```python
# Returns immediately; executes in background task
result = await executor.start_mission(mission.id, background=True)
assert result.status == MissionState.RUNNING

# Check progress later
progress = executor.get_progress(mission.id)
print(f"{progress.completed}/{progress.total_workflows} workflows done")
```

## Pause / Resume

```python
# Start mission in background
task = asyncio.create_task(executor.start_mission(mission.id))

# Pause after first workflow completes
await asyncio.sleep(0.1)
pause_result = await executor.pause_mission(mission.id)
assert pause_result.status == MissionState.PAUSED

# Resume later; checkpoints restore execution state
resume_result = await executor.resume_mission(mission.id)
```

## Checkpoint Recovery

Every completed workflow triggers an automatic checkpoint save.
On resume, the latest checkpoint restores:

- Completed/failed workflow sets
- Mission context (shared data across workflows)
- Mission state

```python
# After resume, checkpoints are loaded automatically
cp = checkpoint_manager.get_latest_checkpoint(mission.id)
print(f"Recovered from checkpoint {cp.id}")
print(f"Workflows completed so far: {cp.completed_workflows}")
```

## Cancellation

```python
cancel_result = await executor.cancel_mission(
    mission.id,
    reason="User cancelled pipeline",
)
assert cancel_result.status == MissionState.CANCELLED
```

## Retry Failed Workflow

```python
result = await executor.start_mission(mission.id)
# ... mission fails on workflow "extract" ...

retry_result = await executor.retry_failed_workflow(mission.id, "extract")
if retry_result.status == MissionState.COMPLETED:
    print("Retry succeeded, mission completed")
```

## Events

| Event | Trigger |
|---|---|
| `MissionCreated` | mission created |
| `MissionStarted` | execution begins |
| `MissionProgressUpdated` | per-workflow progress |
| `MissionCheckpointSaved` | checkpoint persisted |
| `MissionCompleted` | all workflows succeed |
| `MissionFailed` | a workflow fails |
| `MissionCancelled` | user cancels |

## Health

```python
health = executor.health()
# {
#   "status": "HEALTHY",
#   "execution_count": 5,
#   "failure_count": 1,
#   "active_missions": 2,
#   "total_missions": 10,
#   "average_latency_ms": 1234.56,
# }
```

## Telemetry

The `MissionTelemetry` struct tracks:

- `mission_duration_ms`
- `completed_workflows`
- `failed_workflows`
- `remaining_workflows`
- `checkpoint_count`
- `resume_count`
- `pause_count`
- `cancel_count`

Available on any `MissionResult` via `result.telemetry`.
