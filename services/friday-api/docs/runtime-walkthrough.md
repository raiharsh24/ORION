# Mission Runtime — Walkthrough

## Overview

The Mission Runtime (Phase 9 Sprint 1) is the autonomous runtime that connects
all subsystems under one lifecycle: intent → plan → resolve → select → execute
→ reflect → memory. It lives in `app/runtime/` (13 files) and is registered as
service `mission_runtime` in the kernel (Step 7r).

## Key Types

| Type | Role |
|------|------|
| `Mission` | Data model: id, request, intent, status, stages, metadata |
| `MissionStateMachine` | 10 states, 17 transitions with validation |
| `Orchestrator` | Single entrypoint chaining all subsystems |
| `Dispatcher` | Strategy-based routing (5 strategies) |
| `MissionExecutor` | Core execution lifecycle (pause/resume/cancel/retry/rollback/checkpoint) |
| `Supervisor` | Timeout detection, failure counting, auto recovery |
| `ReflectionEngine` | Bottleneck detection, lessons learned, experience storage |
| `TelemetryCollector` | Per-mission metrics (latency, retries, utilization) |
| `RuntimeMetrics` | Aggregated runtime snapshots |

## Lifecycle

```
created → planning → ready → running → completed → archived
                                ↓
                             paused → running
                                ↓
                             failed → recovering → running
```

## How To Use

```python
from app.runtime.runtime import MissionRuntime

runtime = MissionRuntime()

# submit and run
result = await runtime.submit_and_run(
    "Build the project",
    intent="build"
)

# inspect
print(result.success, result.mission_id)

# batch
r1 = await runtime.submit_and_run("request 1", "intent1")
r2 = await runtime.submit_and_run("request 2", "intent2")

# metrics
m = runtime.metrics()
print(m.total_missions, m.average_planning_latency_ms)

# telemetry
t = runtime.telemetry_summary()
print(t["total_missions"], t["success_rate"])

# health
h = runtime.health()
print(h.status, h.running_missions)
```

## Dispatcher Strategies

| Strategy | Trigger | Backend Required |
|----------|---------|------------------|
| `SINGLE_AGENT` | First agent in list | `agent_manager` |
| `PARALLEL_AGENTS` | Multiple agents in list | `agent_manager` |
| `WORKFLOW_ENGINE` | `dispatch_strategy` metadata or keyword `workflow` | `workflow_engine` |
| `TOOL_EXECUTION` | `dispatch_strategy` metadata or keyword `tool` | `tool_executor` |
| `PLUGIN_EXECUTION` | Config directive | Plugin runtime |

## Checkpoint Model

The executor snapshots mission state after every stage transition:

```python
Checkpoint(
    mission_id="m1",
    stage="planning",
    data={"status": "planning", "stages": 0, "metadata": {}},
    timestamp=1234567890.0,
)
```

Checkpoints enable `rollback_mission()` to restore to the last good state.

## Supervisor Recovery

The supervisor monitors timeouts and failures:

- `watch_timeout(mission_id, timeout_s)` — register a timeout window
- `check_timeouts()` — returns list of timed-out mission IDs
- `record_failure(mission_id)` — increment failure counter
- `can_retry(mission_id, max_retries=3)` — check if retry budget remains
- `recover_timeout(mission_id)` — return action (retry or escalate)
- `recover_failure(mission_id, error)` — return action with recovery metadata

Recovery success rate is tracked automatically.

## Reflection Model

Each mission reflection produces:

- **Lessons** — category (performance, failure, bottleneck), description, severity, recommendation
- **Bottlenecks** — identified from stage duration exceeding thresholds
- **Experiences** — stored with category, outcome, and telemetry for future reference

## Events

| Event | Payload |
|-------|---------|
| `MissionStarted` | mission_id, intent, request |
| `MissionPaused` | mission_id |
| `MissionResumed` | mission_id |
| `MissionCompleted` | mission_id, duration_ms, stages_completed |
| `MissionFailed` | mission_id, stage, error |
| `MissionRecovered` | mission_id, recovery_attempt |
| `MissionArchived` | mission_id |

## File Layout

```
app/runtime/
├── __init__.py          # Public API exports
├── base.py              # Mission, MissionStage, ExecutionResult, RecoveryAction
├── state.py             # MissionStateMachine (10 states, 17 transitions)
├── orchestrator.py      # Orchestrator — single entrypoint
├── dispatcher.py        # DispatchStrategy, DispatchDecision, Dispatcher
├── executor.py          # MissionExecutor — lifecycle + checkpoint
├── supervisor.py        # Supervisor — timeout + failure + recovery
├── reflection.py        # ReflectionEngine — lessons + bottlenecks + experiences
├── telemetry.py         # TelemetryCollector — per-mission metrics
├── metrics.py           # RuntimeMetrics — aggregated snapshots
├── events.py            # 7 event types
├── health.py            # RuntimeHealth model
└── runtime.py           # MissionRuntime — top-level facade
```

## Dependencies

- Stdlib only: `time`, `uuid`, `datetime`, `dataclasses`, `typing`, `asyncio`
- Internal: `app.runtime.*`, `app.runtime.dispatcher.Dispatcher`
