# Mission Runtime — Integration Architecture

## Overview

Phase 9 Sprint 2 integrates 10 production subsystems into the runtime,
replacing all placeholder dispatch logic with real execution through the
kernel's dependency injection.

## Integrated Subsystems

| Subsystem | DI Name | How the Runtime Uses It |
|-----------|---------|------------------------|
| PlanningEngine | `planning_engine` | `create_goal()`, `generate_plan()` → produces Plan with steps |
| WorkflowExecutor | `workflow_engine_v2` | `execute(graph)` → executes DAG-based workflows |
| CapabilityResolver | `capability_resolver` | `resolve(action_id)` → resolves tool IDs for plan steps |
| CapabilityRegistry | `capability_registry_v2` | `list_capabilities()` → enumerates available capabilities |
| ToolSelectionEngine | `tool_selection_engine` | `select(context)` → picks optimal tools for mission |
| ToolExecutionEngine | `tool_execution_engine` | `execute(selection_result)` → runs selected tools |
| AgentManager | `agent_manager` | `execute_task()`, `list_agents()` → single/parallel agent dispatch |
| MemoryManager | `memory_engine` | `get_working_memory()`, `retrieve_relevant_context()` → stores mission results |
| PluginRuntime | `plugin_runtime` | `execute(plugin_id, coro)` → runs plugin-based missions |
| MissionEngine | `mission_engine_v2` | Used via WorkflowExecutor for graph execution |

## Data Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     Orchestrator.run_lifecycle()                │
│                                                                │
│  1. Planning                                                   │
│     └─ PlanningEngine.create_goal(name, description)           │
│     └─ PlanningEngine.generate_plan(goal) → Plan               │
│                                                                │
│  2. Capability Resolution                                      │
│     └─ CapabilityResolver.resolve(action_id) → tool_ids        │
│     └─ CapabilityRegistry.list_capabilities()                  │
│     └─ AgentManager.list_agents().capabilities                 │
│                                                                │
│  3. Tool Selection                                             │
│     └─ ToolSelectionEngine.select(                             │
│          ToolSelectionContext(capabilities))                    │
│        → ToolSelectionResult(tool_ids)                         │
│                                                                │
│  4. Workflow Generation                                        │
│     └─ Build WorkflowGraph from Plan steps                     │
│     └─ WorkflowExecutor.execute(graph)                         │
│                                                                │
│  5. Execution                                                  │
│     └─ MissionExecutor.execute_mission(                        │
│          mission, plan, selection_result)                      │
│        │                                                       │
│        ├─ SINGLE_AGENT → AgentManager.execute_task()           │
│        ├─ PARALLEL    → AgentManager.execute_task() × N        │
│        ├─ WORKFLOW    → WorkflowExecutor.execute(graph)        │
│        ├─ TOOL        → ToolExecutionEngine.execute(result)    │
│        └─ PLUGIN      → PluginRuntime.execute(id, mission)     │
│                                                                │
│  6. Reflection                                                 │
│     └─ ReflectionEngine.reflect(mission, result, telemetry)    │
│        → ReflectionReport(lessons, bottlenecks)                │
│                                                                │
│  7. Memory Update                                              │
│     └─ MemoryManager.get_working_memory().set(key, value)      │
│     └─ MemoryManager.retrieve_relevant_context(query)          │
│                                                                │
│  8. Persistence                                                │
│     └─ MissionStore.save_mission() — every state change        │
│     └─ MissionStore.save_telemetry() — after completion        │
│     └─ MissionStore.save_reflection() — after reflection       │
│     └─ MissionStore.save_checkpoint() — at each lifecycle step │
└────────────────────────────────────────────────────────────────┘
```

## Pipeline Orchestration (Dispatcher)

The `Dispatcher` selects execution strategy based on these signals (in order):

1. **Metadata override** — `mission.metadata["dispatch_strategy"]` explicitly set
2. **Keyword match** — user_request contains workflow/plugin/tool keywords
3. **Agent availability + plan complexity** — multiple goals → parallel agents
4. **Default** — single agent if available, else workflow engine

No placeholder dispatch remains. Every strategy routes to a real backend.

## Mission Queue Architecture

```
         ┌─────┐
         │User │
         └──┬──┘
            ▼
    ┌───────────────┐
    │  MissionQueue  │
    │  (heapq +      │
    │   asyncio)     │
    └───┬───────┬────┘
        │       │
   ┌────▼──┐ ┌──▼────────┐
   │Priority│ │Dependency │
   │ Order  │ │ Gate      │
   └────────┘ └───────────┘
        │
        ▼
  ┌──────────┐
  │ Semaphore│  (max_concurrent)
  └────┬─────┘
       │
  ┌────▼──────────┐
  │  _queue_handler│ → Orchestrator.run_lifecycle()
  └───────────────┘
       │
  ┌────▼────┐
  │ Timeout │
  │ Watch   │
  └─────────┘
```

## Persistence Architecture (MissionStore)

```
     ~/.friday/missions/
     ├── {mission_id}.json           → MissionRecord
     ├── {mission_id}_telemetry.json → TelemetryRecord
     ├── {mission_id}_checkpoint.json→ CheckpointRecord
     └── {mission_id}_reflection.json→ dict
```

File-per-mission design allows concurrent access and simple recovery.
On restart, `load_all_active()` reconstructs missions from `running`,
`paused`, or `recovering` states.

## Duplicate Analysis

| Component | Runtime | Duplicate? | Resolution |
|-----------|---------|------------|------------|
| MissionStateMachine | 10 states (created–archived) | No — higher level than MissionEngine's 6-state enum | Keep both |
| Dispatcher | Strategy selector | No — unique heuristic routing layer | Keep |
| Supervisor | Timeout + failure + recovery | No — no equivalent elsewhere | Keep |
| ReflectionEngine | Bottleneck + lesson extraction | No — no equivalent elsewhere | Keep |
| TelemetryCollector | Per-mission metrics | No — runtime-specific scope | Keep |
| RuntimeMetrics | Aggregated snapshots | No — runtime-specific scope | Keep |
| MissionQueue | Priority + deps + semaphore | No — new in Sprint 2 | Keep |
| MissionStore | JSON persistence | No — new in Sprint 2 | Keep |
| MissionExecutor | Dispatch+execution | Complementary to mission_engine's MissionExecutor | Keep |

## Runtime API

| Method | Purpose |
|--------|---------|
| `submit(user_request, intent, priority, dep_ids, timeout)` | Create + queue |
| `run(mission)` | Execute immediately |
| `submit_and_run(...)` | Create + queue + wait |
| `submit_background(...)` | Create + queue, return mission_id |
| `pause(mission_id)` | Pause execution |
| `resume(mission_id)` | Resume from pause |
| `cancel(mission_id)` | Cancel queued or running |
| `retry(mission_id)` | Re-queue failed mission |
| `archive(mission_id)` | Archive completed/failed |
| `get_status(mission_id)` | Current status string |
| `get_history(limit)` | Recent mission summaries |
| `queue_status()` | Queue depth/activity |
| `health()` | RuntimeHealth dataclass |
| `get_telemetry(mission_id)` | Per-mission telemetry |
| `metrics()` | RuntimeMetricsSnapshot |
| `telemetry_summary()` | Aggregated telemetry |
