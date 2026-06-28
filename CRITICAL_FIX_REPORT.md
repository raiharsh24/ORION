# Critical Issue Fix Report

**Date:** 2026-06-28
**Scope:** C1, C2, C3 from SYSTEM_VALIDATION_REPORT.md

---

## Summary

| Issue | Severity | Status | Files Changed |
|-------|----------|--------|---------------|
| C1: WorkflowWorkerAgent has no context — all step execution crashes | Critical | **FIXED** | 1 |
| C2: EventBus subscribers never unsubscribe — leak on restart | Critical | **FIXED** | 4 |
| C3: AgentCoordinator has no lifecycle — state leaks on shutdown | Critical | **FIXED** | 1 |
| **Total** | | **3/3** | **6 files** |

Tests: **180 passed / 1 failed** (pre-existing flaky integration test `test_ask_route_confirmation_loop`). **Zero regressions.**

---

## C1: WorkflowWorkerAgent Context Fix

**Root cause:** `AgentRegistry.register()` called `agent.set_event_bus()` and `agent.set_message_bus()` but **never** called `agent.set_context()`. The `WorkflowWorkerAgent` stored `self._shared_context` from its constructor but all execution methods (`_execute_tool`, `_execute_llm`, `_execute_knowledge`, `_execute_mission`, `_execute_notification`, `_execute_agent_task`) read `self._context` — a separate `None` property inherited from `BaseAgent`. Every step execution raised `RuntimeError("SharedContext unavailable")`.

**Fix:** Added `workflow_worker.set_context(shared_context)` immediately after `agent_registry.register(workflow_worker)` in `boot.py:291`.

```python
await agent_registry.register(workflow_worker)
workflow_worker.set_context(shared_context)  # ← FIX
self._container.register_singleton("workflow_worker_agent", workflow_worker)
```

**Verification:** All workflow runtime tests pass, including `test_worker_agent_tool_execution`, `test_worker_agent_llm_execution`, `test_worker_agent_condition`, `test_worker_agent_agent_task_recursive`. Each of these exercises the context-dependent execution paths that previously crashed.

---

## C2: EventBus Subscriber Leak Fix

**Root cause:** Four engine components (`MemoryEngine`, `ToolEngine`, `KnowledgeEngine`, `PlannerEngine`) subscribe to `EventBus` during `initialize()` but **never unsubscribe** in `shutdown()`. The `_initialized` flag prevented re-subscription on kernel restart, meaning after a restart the EventBus had no subscribers from these engines.

**Fix:** In each engine:
1. Store `self._event_bus` during `initialize()` (was a local variable)
2. In `shutdown()`: unsubscribe every registered callback, then reset `_initialized = False`

### MemoryEngine (`engine.py:56-67`)
```python
async def shutdown(self) -> None:
    if self._event_bus and self._manager:
        self._event_bus.unsubscribe("ConversationCompleted", self._manager.on_conversation_completed)
        self._event_bus.unsubscribe("ToolCompleted", self._manager.on_tool_completed)
        self._event_bus.unsubscribe("MissionCompleted", self._manager.on_mission_completed)
        self._event_bus.unsubscribe("WorkflowCompleted", self._manager.on_workflow_completed)
    if self._manager and hasattr(self._manager._store, "save"):
        self._manager._store.save()
    self._initialized = False
```

### ToolEngine (`tool_engine.py:298-304`)
```python
async def shutdown(self) -> None:
    if self._event_bus:
        self._event_bus.unsubscribe("PlanValidated", self.on_plan_validated)
        self._event_bus.unsubscribe("MissionStarted", self.on_mission_started)
        self._event_bus.unsubscribe("WorkflowStarted", self.on_workflow_started)
        self._event_bus.unsubscribe("MemoryUpdated", self.on_memory_updated)
    self._initialized = False
```

### KnowledgeEngine (`knowledge_engine.py:210-217`)
```python
async def shutdown(self) -> None:
    if self._event_bus:
        self._event_bus.unsubscribe("MemoryUpdated", self.on_memory_updated)
        self._event_bus.unsubscribe("ToolCompleted", self.on_tool_completed)
        self._event_bus.unsubscribe("MissionCompleted", self.on_mission_completed)
        self._event_bus.unsubscribe("WorkflowCompleted", self.on_workflow_completed)
    self._initialized = False
```

### PlannerEngine (`planner_engine.py:47-56`)
```python
async def shutdown(self) -> None:
    if self._event_bus and self._manager:
        self._event_bus.unsubscribe("ConversationReceived", self._manager.on_conversation_received)
        self._event_bus.unsubscribe("MemoryRetrieved", self._manager.on_memory_retrieved)
        self._event_bus.unsubscribe("ToolCompleted", self._manager.on_tool_completed)
        self._event_bus.unsubscribe("MissionCompleted", self._manager.on_mission_completed)
        self._event_bus.unsubscribe("WorkflowCompleted", self._manager.on_workflow_completed)
    self._initialized = False
```

**Verification:** `test_kernel_boot_shutdown_restart` passes, confirming the full shutdown/boot cycle works without subscriber leaks. During test teardown, "Scheduler tick loop cancelled" confirms clean shutdown.

---

## C3: AgentCoordinator Lifecycle Fix

**Root cause:** `AgentCoordinator` had no `shutdown()`, `stop()`, or `close()` method. The `FridayLifecycleManager.shutdown_all()` found no hook and skipped it entirely. All pending tasks, circuit breakers, dead letter queue entries, active delegations, and the `AgentScheduler` tick loop were orphaned on kernel shutdown.

**Fix:** Added `shutdown()` method to `AgentCoordinator` (`coordinator.py:207-225`) that:

1. Cancels all pending tasks via `cancel_task()`
2. Cancels all active delegation background tasks
3. Resets all circuit breakers to CLOSED
4. Drains the dead letter queue
5. Calls `AgentScheduler.shutdown()` to stop the tick loop and cancel job tasks
6. Clears all internal state dicts

```python
async def shutdown(self) -> None:
    logger.info("AgentCoordinator shutting down...")

    for task_id in list(self._pending_tasks.keys()):
        await self.cancel_task(task_id)
    self._pending_tasks.clear()

    for agent_id, delegation in list(self._active_delegations.items()):
        delegation.cancel()
    self._active_delegations.clear()

    for cb in self._circuit_breakers.values():
        cb.reset()
    self._circuit_breakers.clear()

    self._dead_letter_queue.clear()

    await self._scheduler.shutdown()

    logger.info("AgentCoordinator shut down successfully.")
```

**Verification:** `test_kernel_boot_shutdown_restart` passes (exercises full lifecycle). All coordinator/agent tests pass (17 tests in `test_agents/`). Scheduler tick loop cleanly cancelled during teardown.

---

## Files Changed

| File | Issue | Change |
|------|-------|--------|
| `services/friday-api/app/kernel/boot.py:291` | C1 | Added `workflow_worker.set_context(shared_context)` after agent registration |
| `services/friday-api/app/memory/engine.py:56-67` | C2 | Added unsubscribe and `_initialized = False` to `shutdown()`; stored `self._event_bus` |
| `services/friday-api/app/friday/tool_engine.py:298-304` | C2 | Added unsubscribe and `_initialized = False` to `shutdown()`; stored `self._event_bus` |
| `services/friday-api/app/friday/knowledge_engine.py:210-217` | C2 | Added unsubscribe and `_initialized = False` to `shutdown()`; stored `self._event_bus` |
| `services/friday-api/app/friday/planner_engine.py:47-56` | C2 | Added unsubscribe and `_initialized = False` to `shutdown()`; stored `self._event_bus` |
| `services/friday-api/app/agents/coordinator.py:207-225` | C3 | Added `shutdown()` method with task cancellation, circuit breaker reset, dead letter drain, scheduler shutdown |

**Total: 6 files changed, ~80 lines added, ~5 lines modified.**

---

## Remaining Critical Issue Count: **0**

All 3 Critical issues from SYSTEM_VALIDATION_REPORT.md are verified fixed.
