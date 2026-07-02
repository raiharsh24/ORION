# Mission Execution Engine Architecture

## Design Principles

1. **Deterministic orchestration** — no LLM or AI in mission execution;
   workflows execute in a planner-defined order.
2. **Layered isolation** — MissionExecutor orchestrates WorkflowExecutor,
   which orchestrates ToolExecutionEngine. Layers never bypass each other.
3. **Stateful resilience** — checkpoints provide pause/resume and crash
   recovery without data loss.
4. **Event-driven observability** — every state transition publishes a
   `FridayEvent` for monitoring, logging, and telemetry.
5. **Stateless scheduler** — `MissionExecutor` manages async tasks but does
   not persist active tasks across process restarts; checkpoints provide
   the recovery basis.

## Package Structure

```
app/mission_engine/
├── __init__.py       # Public API exports
├── base.py           # Core models: Mission, MissionState, MissionContext,
│                     #   MissionCheckpoint, MissionProgress, MissionTelemetry,
│                     #   MissionResult
├── mission.py        # MissionStore — in-memory mission CRUD
├── planner.py        # MissionPlanner — creates missions, orders workflows
├── executor.py       # MissionExecutor — main orchestrator
├── checkpoint.py     # CheckpointManager — save/load/recover
├── events.py         # 7 FridayEvent subtypes
└── result.py         # build_mission_result helper
```

## Core Models

### MissionState
```
PENDING → RUNNING → COMPLETED
                   → FAILED
                   → CANCELLED
         RUNNING → PAUSED → RUNNING
```

### Mission
| Field | Type | Description |
|---|---|---|
| `id` | `str` | UUID |
| `name` | `str` | Human-readable name |
| `state` | `MissionState` | Current lifecycle phase |
| `priority` | `MissionPriority` | LOW / MEDIUM / HIGH / CRITICAL |
| `workflow_ids` | `List[str]` | Ordered list of workflow graph IDs |
| `metadata` | `Dict` | User-defined key/value store |
| `created_at` | `datetime` | Creation timestamp |
| `started_at` | `Optional[datetime]` | First RUNNING transition |
| `completed_at` | `Optional[datetime]` | Terminal transition timestamp |
| `error` | `Optional[str]` | Failure reason |

### MissionContext
Shared data space across workflows within a mission.
- `shared_data`: flat key/value dict (populated by node outputs)
- `workflow_outputs`: per-workflow result dicts
- `node_outputs`: flattened per-node outputs keyed as `"{wf_id}.{node_id}"`

### MissionCheckpoint
Snapshot of mission state for recovery.
- `mission_state`, `completed_workflows`, `failed_workflows`
- `running_workflow`, `context` snapshot

## Data Flow

```
create_mission(name, workflow_graphs)
  │
  ├─ WorkflowValidator.validate() each graph
  ├─ MissionStore.create()
  ├─ register_workflow_graph() for each graph
  └─ publish MissionCreated
       │
start_mission(mission_id)
  │
  ├─ state validation (not running, not terminal)
  ├─ MissionStore.update_state(RUNNING)
  ├─ publish MissionStarted
  │
  ├─ for each workflow_id in plan_sequential():
  │    ├─ WorkflowExecutor.execute(graph)
  │    ├─ CheckpointManager.save()
  │    ├─ publish MissionCheckpointSaved
  │    ├─ update MissionProgress
  │    ├─ publish MissionProgressUpdated
  │    └─ on failure: publish MissionFailed, break
  │
  ├─ determine_final_state()
  ├─ publish MissionCompleted / MissionFailed
  └─ return MissionResult
```

## Checkpoint Recovery Flow

```
resume_mission(mission_id)
  │
  ├─ validate mission.state == PAUSED
  ├─ CheckpointManager.get_latest_checkpoint()
  ├─ CheckpointManager.recover() — restores state + context
  ├─ restore completed/failed workflow sets
  ├─ increment resume_count telemetry
  └─ _execute_mission() — resumes from checkpoint
```

## Error Handling

- **Workflow graph not found**: mission FAILED immediately
- **Failed workflow**: mission FAILED, remaining workflows skipped
- **Exception during execution**: mission FAILED with exception message
- **Cancellation during workflow**: mission CANCELLED, remaining skipped
- **Retry**: `retry_failed_workflow()` re-executes a single failed workflow;
  if all remaining workflows then succeed, mission completes

## Performance Characteristics

- Mission creation: O(n) where n = workflow count (validation)
- Sequential execution: O(w × t) where w = workflows, t = tool nodes
- Checkpoint save: O(1)
- Checkpoint recovery: O(1)
- Health check: O(1)

## Dependencies

| Component | Dependency | Purpose |
|---|---|---|
| `MissionExecutor` | `WorkflowExecutor` | DAG execution for each workflow |
| `MissionExecutor` | `MissionStore` | In-memory mission CRUD |
| `MissionExecutor` | `CheckpointManager` | Pause/resume state |
| `MissionExecutor` | `MissionPlanner` | Workflow ordering |
| `MissionExecutor` | `EventBus` | Event publishing |
| `MissionPlanner` | `WorkflowValidator` | Graph validation |
