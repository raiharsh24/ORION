# Remaining Technical Debt

## Critical (blocks production use)

| # | Issue | File | Description |
|---|-------|------|-------------|
| C1 | **Workflow Runtime disconnected** | `app/workflow_runtime/` | Fully tested (61 tests) but has no API routes and is not reachable. |
| C2 | **RuntimeSchedulerBridge never called** | `app/workflow_runtime/scheduler_bridge.py` | Registered in kernel but `submit_plan()` never invoked from any orchestration path. |
| C3 | **FridayScheduler is placeholder** | `app/scheduler/scheduler.py` | `start()` and `stop()` are `pass` with TODOs. |

## High (structural impact)

| # | Issue | File | Description |
|---|-------|------|-------------|
| H1 | **Three parallel capability registries** | `capabilities/`, `kernel/capability.py`, `friday/capability_registry.py` | Different schemas, no synchronization. |
| H2 | **Fire-and-forget event tasks** | 4 locations | `loop.create_task()` used without tracking. Tasks silently lost on shutdown. |
| H3 | **Workflow Runtime not in KernelHealth** | `app/kernel/kernel.py` | No `workflow_runtime` field in health model. |
| H4 | **Event bus subscriptions never unsubscribed** | `app/events/bus.py` | No `unsubscribe()` called during shutdown. |
| H5 | **Missing web search tool** | `app/friday/planner_manager.py` | Web search intent maps tool_name="browser" but no real web search plugin integrated. |

## Medium

| # | Issue | Description |
|---|--------|-------------|
| M1 | **No tool execution delegation to WorkflowRuntime from UnifiedEngine** | The engine supports `_runtime_bridge` as an optional path but it's not the default. |
| M2 | **Streaming pipeline does not emit per-stage events** | `execute_stream` runs stages inline without progress events. |
| M3 | **Cancellation not wired into API layer** | No HTTP endpoint to cancel an in-flight execution. The `cancel()` method exists but has no route. |
| M4 | **Knowledge retrieval not integrated into execution** | `KnowledgeEngine` exists but is not called from the execution pipeline. CognitiveCore provides semantic search instead. |
| M5 | **Plugin hooks not tested end-to-end** | `PluginHookMiddleware` calls plugin hooks but no test verifies plugin hook execution. |

## Low

| # | Issue | Description |
|---|--------|-------------|
| L1 | **Duplicate string literals for service names** | ~30 hardcoded strings in `boot.py`. |
| L2 | **Hardcoded workspace path** | `app/core/dependencies.py:20` has `/home/warlock/ORION`. |
| L3 | **SharedContext property lookups bypass DI** | Each property calls `kernel.get_service()` on every access. |
| L4 | **Policies subsystem unimplemented** | `app/policies/` — all stubs with `pass`. |

## Previously Documented (from RUNTIME_VALIDATION_REPORT.md)

These issues from the original validation report remain unchanged:

| Ref | Issue | Priority |
|-----|-------|----------|
| C1 | Planner→WorkflowRuntime type mismatch | Critical |
| C2 | Workflow Runtime has no API endpoints | Critical |
| C3 | FridayOrchestrator bypasses both workflow systems | Critical |
| H1 | FridayScheduler is placeholder | High |
| H2 | ToolEngine event handlers are stubs | High |
| H3 | Three parallel capability registries | High |
| H4 | Fire-and-forget event tasks | High |
| H5/H6 | Kernel health omits workflow_runtime | High |
| M1-M8 | Medium issues (see validation report) | Medium |
| L1-L5 | Low issues (see validation report) | Low |

## Summary

| Category | Count |
|----------|-------|
| Critical | 3 |
| High | 5 |
| Medium | 5 |
| Low | 4 |
| Pre-existing (from M1-M3) | 16 |
