# ORION Runtime Validation Report

**Date:** 2026-06-28  
**Scope:** Alpha 4.0 Kernel through Alpha 5.0 Workflow Runtime  
**Methodology:** Static code analysis of `app/` (43 files), `tests/` (157 tests), configuration, and wiring.

---

## 1. Execution Flow Trace

```
User Request (HTTP /ask or /chat)
  │
  ▼
app/orion/orchestrator.py :: OrionOrchestrator.process_query()
  │
  ├── IntentClassifier.classify()           → IntentType
  ├── Planner.plan(prompt, intent)          → ExecutionPlan
  │     └── PlannerManager.create_plan()     → LLM call, IntentAnalyzer, GoalExtractor, TaskClassifier
  │
  ├── [TYPE MISMATCH] ExecutionPlan produced, BUT:
  │     Workflow Runtime expects ExecutionPlanInput
  │     No adapter exists → FLOW BREAKS HERE
  │
  ├── ToolExecutor.execute(plan)             → Direct tool calls (bypasses workflow runtime)
  ├── LLMRouter.generate(prompt)             → LLM response
  └── MemoryEngine.store(session)            → ConversationMemory
  │
  ▼
OrionResponse returned to client
```

**Current reality:** The `/ask` and `/chat` endpoints bypass the Workflow Runtime entirely. `OrionOrchestrator` calls tools directly via `ToolExecutor` after the Planner produces an `ExecutionPlan`. The Workflow Runtime (Alpha 5.0) is registered in the kernel `boot.py` Step 12 but is **never invoked by any API endpoint or orchestrator path**.

**The intended flow through Alpha 5.0 would be:**

```
User Request
  → Planner (ExecutionPlan)
  → Adapter (ExecutionPlan → ExecutionPlanInput)  ← MISSING
  → RuntimeSchedulerBridge.submit_plan()
  → WorkflowRuntimeManager.start_from_plan()
  → WorkflowRuntimeExecutor.build_from_plan()
  → WorkflowRuntimeExecutor.execute_step()
  → AgentCoordinator.delegate()
  → WorkflowWorkerAgent.execute_task()
  → SharedContext.execute_tool() / generate_llm() / query_knowledge()
  → ToolEngine / LLMRouter / KnowledgeEngine
  → EventBus publishes completion events
  → MemoryEngine captures results
  → Response assembled
```

---

## 2. Issues by Category

### 2.1 Critical Issues

| # | Issue | File | Description |
|---|-------|------|-------------|
| C1 | **Planner→WorkflowRuntime type mismatch** | `app/orion/planner_schema.py` vs `app/workflow_runtime/models.py` | `PlannerManager.create_plan()` returns `ExecutionPlan`. `RuntimeSchedulerBridge.submit_plan()` expects `ExecutionPlanInput`. They share only `goal` and `steps`. No adapter exists. **The workflow runtime cannot receive plans from the planner.** |
| C2 | **Workflow Runtime has no API endpoints** | `app/api/` | All 10 workflow API routes (`/api/workflows/*`) call `WorkflowEngine` (Alpha 4.0). Zero routes call `WorkflowRuntimeManager` or `RuntimeSchedulerBridge`. The runtime is registered in the kernel but unreachable from outside. |
| C3 | **OrionOrchestrator bypasses both workflow systems** | `app/orion/orchestrator.py` | `process_query()` uses `ToolExecutor` directly. It does not consult `WorkflowEngine`, `WorkflowRuntimeManager`, or any workflow subsystem. The entire workflow layer is disconnected from the request path. |

### 2.2 High Issues

| # | Issue | File | Description |
|---|-------|------|-------------|
| H1 | **OrionScheduler is a placeholder** | `app/scheduler/scheduler.py` | `start()` and `stop()` are `pass` with TODOs. Cron scheduling in `RuntimeSchedulerBridge.schedule_plan()` will call `agent_scheduler.schedule()` but the `OrionScheduler` itself does nothing. |
| H2 | **ToolEngine event handlers are stubs** | `app/orion/tool_engine.py:287-303` | Four subscribe handlers (`on_plan_validated`, `on_mission_started`, `on_workflow_started`, `on_memory_updated`) only log. They do not execute any tool logic, validate plans, or respond to events. |
| H3 | **Three parallel capability registries** | `app/capabilities/registry.py`, `app/kernel/capability.py`, `app/orion/capability_registry.py` | Three separate registries with different schemas, no synchronization. The kernel's `OrionCapabilityRegistry` is populated during boot with 9 capabilities. `app/capabilities/` is ABC-based with `BaseCapability`. `app/orion/capability_registry.py` has its own Pydantic `CapabilityMetadata`. ToolEngine uses the third one. |
| H4 | **Fire-and-forget event tasks (orphaned coroutines)** | 4 locations | `tool_engine.py:104`, `memory/manager.py:108`, `agents/scheduler.py:141`, `workflow_runtime/manager.py:308` all use `loop.create_task(self._event_bus.publish(event))` without tracking. On shutdown, these are silently lost. If publish hangs, tasks accumulate. |
| H5 | **Kernel health() omits workflow_runtime** | `app/kernel/kernel.py:246-312` | `KernelHealth` Pydantic model has fields: planner, knowledge, memory, desktop, mission, workflow, scheduler, llm, agents. No `workflow_runtime` field. The health check does not call `workflow_runtime_manager.health()`. |
| H6 | **SchedulerBridge health not wired into boot** | `app/kernel/boot.py:308-312` | `RuntimeSchedulerBridge` is created but its `health()` method is never called by any health aggregation. |

### 2.3 Medium Issues

| # | Issue | File | Description |
|---|-------|------|-------------|
| M1 | **Dead code: `app/workflow/` duplicates `app/workflow_runtime/` semantics** | `app/workflow/graph.py` | `get_parallel_groups()` exists in both `app/workflow/graph.py` (line 136, operating on `Workflow` objects) and `app/workflow_runtime/models.py` (line 94, operating on `RuntimeWorkflow`). The old one is dead code if workflow_runtime is the future. |
| M2 | **Dead code: `app/orion/planner.py` unused imports** | `app/orion/planner.py` | Imports `ToolPlan`, `re` at module level that are never used. These are artifacts from the refactor. |
| M3 | **Dead code: `app/kernel/kernel.py` `register_service()` called from shutdown** | `app/kernel/kernel.py:157-159` | `shutdown()` iterates `list_services()` and calls `unregister_service()` for each. But shutdown is handled by `OrionLifecycleManager.shutdown_all()` which already handles proper lifecycle. The manual loop is redundant. |
| M4 | **`WorkflowWorkerAgent` registered during boot but never sent tasks** | `app/kernel/boot.py:285-291` | The `WorkflowWorkerAgent` is registered with `agent_registry`. However, no code path currently creates `AgentTask` objects that would route to `step_type` values matching the worker's capabilities. |
| M5 | **Race condition: `_run_workflow` can be invoked multiple times** | `app/workflow_runtime/manager.py` | `resume()` and `retry_step()` both create new `asyncio.create_task(self._run_workflow(workflow_id))` without checking if a task already exists for the same `workflow_id`. Double-start is possible. |
| M6 | **JSON serialization may fail for complex types** | `app/workflow_runtime/persistence.py:40` | Uses `json.dump(workflow.model_dump(mode="json"), ...)` but `mode="json"` may fail on datetime objects with timezone or custom types. `datetime.now(timezone.utc)` produces timezone-aware objects. |
| M7 | **No workflow_runtime route registered in FastAPI** | `app/api/__init__.py` | The `api_router` has 8 sub-routers. None includes workflow_runtime endpoints. The subsystem is unreachable via HTTP. |
| M8 | **Event leak: event bus subscriptions never unsubscribed** | `app/events/bus.py` | `subscribe()` adds callbacks to a dict. No `unsubscribe` is called during shutdown anywhere in the codebase. Subscriber references accumulate until the kernel object is destroyed. |

### 2.4 Low Issues

| # | Issue | File | Description |
|---|-------|------|-------------|
| L1 | **Duplicate string literals for service names** | `app/kernel/boot.py` | Service names like `"knowledge_engine"`, `"mission_engine"` hardcoded as strings ~30 times. No `ServiceNames` constants class. |
| L2 | **`app/core/dependencies.py` uses absolute workspace path** | `app/core/dependencies.py:20` | `workspace_root = "/home/warlock/ORION"` is hardcoded. Should use the kernel config. |
| L3 | **`SharedContext` property lookups bypass DI container** | `app/agents/context.py:22-36` | Each property calls `self._kernel.get_service(name)` on every access, making repeated O(n) lookups. Could cache at construction time. |
| L4 | **Policies subsystem entirely unimplemented** | `app/policies/` | `confirmation.py`, `permissions.py`, `safety.py` are all stubs with TODOs and `pass`. They are imported but their methods are never called. |
| L5 | **`app/agents/context.py` `query_knowledge` ignores `top_k`** | `app/agents/context.py:87` | Calls `self.knowledge.retrieve(query, top_k=top_k)` but the `KnowledgeEngine.retrieve()` method signature should be verified for `top_k` parameter. |

---

## 3. Subsystem Wiring Verification

| Subsystem | Registered in Kernel Boot | Has API Routes | Called from Orchestrator | Health Checked | Has Tests |
|-----------|:---:|:---:|:---:|:---:|:---:|
| EventBus | ✅ Step 3 | ❌ | ✅ | ❌ | ✅ |
| MemoryEngine | ✅ Step 4 | ✅(2 routes) | ✅ | ✅ | ✅ |
| KnowledgeEngine | ✅ Step 5 | ✅(3 routes) | ✅ | ✅ | ✅ |
| PlannerEngine | ✅ Step 6 | ❌ | ✅ | ✅ | ✅ |
| DesktopController | ✅ Step 7 | ❌ | ❌ | ✅ | ✅ |
| DesktopAutomation | ✅ Step 7b | ❌ | ❌ | ✅(merged) | ✅ |
| ToolEngine | ✅ Step 7c | ❌ | ✅via ToolExecutor | ✅ | ✅ |
| MissionEngine | ✅ Step 8 | ✅(9 routes) | ❌ | ✅ | ✅ |
| WorkflowEngine | ✅ Step 9 | ✅(10 routes) | ❌ | ✅ | ✅ |
| OrionScheduler | ✅ Step 10 | ❌ | ❌ | ✅ | ❌ |
| LLMRouter | ✅ Step 10b | ❌ | ✅ | ✅ | ❌ |
| AgentCoordinator | ✅ Step 11 | ❌ | ❌ | ✅ | ✅(8 test files) |
| **WorkflowRuntime** | **✅ Step 12** | **❌** | **❌** | **❌** | **✅(61 tests)** |

**Key finding:** 6 of 13 subsystems have no API routes. 4 of 13 are not called from the orchestrator. 1 (WorkflowRuntime) is fully tested but completely disconnected from the running system.

---

## 4. Dependency Graph

```
User Request
  │
  ├── app/api/routes.py (POST /ask, /chat)
  │     └── app/orion/orchestrator.py
  │           ├── app/orion/intent.py (IntentClassifier)
  │           ├── app/orion/planner.py → PlannerEngine → PlannerManager → LLMRouter
  │           ├── app/orion/tool_executor.py → ToolEngine → ToolResolver → ToolRegistry → app/tools/*
  │           │     └── app/orion/capability_registry.py
  │           │     └── app/orion/permissions.py
  │           │     └── app/orion/sandbox.py
  │           ├── app/llm/router.py → GeminiAdapter
  │           ├── app/memory/engine.py → MemoryManager
  │           │     └── app/memory/conversation.py
  │           │     └── app/memory/embeddings.py → EmbeddingsManager
  │           └── app/orion/prompts.py (PromptManager)
  │
  ├── app/api/workflows.py (10 routes)
  │     └── app/workflow/engine.py → WorkflowRunner → WorkflowNodeExecutor
  │           ├── app/workflow/workflow.py
  │           ├── app/workflow/history.py (WorkflowHistory)
  │           ├── app/workflow/templates.py
  │           └── app/workflow/graph.py
  │
  ├── app/api/missions.py (9 routes)
  │     └── app/missions/mission_manager.py
  │           ├── app/missions/mission.py
  │           ├── app/missions/mission_history.py
  │           └── app/missions/telemetry.py
  │
  └── [GAP] No routes call:
        └── app/workflow_runtime/ ── NOT REACHABLE ──
              ├── RuntimeSchedulerBridge
              ├── WorkflowRuntimeManager
              ├── WorkflowRuntimeExecutor
              ├── WorkflowPersistence
              ├── CheckpointManager
              └── WorkflowWorkerAgent → AgentCoordinator → AgentMessageBus
                    ├── AgentRegistry
                    ├── AgentScheduler → CircuitBreaker → RetryHandler → DeadLetterQueue
                    ├── AgentTelemetry
                    └── SharedContext → ToolEngine, LLMRouter, KnowledgeEngine, MemoryEngine
```

---

## 5. Service Graph (DI Container)

```
OrionServiceContainer
  │
  ├── "event_bus"                 ─── EventBus (Step 3)
  ├── "memory_engine"             ─── ConversationMemory (Step 4, from core.dependencies)
  ├── "knowledge_engine"          ─── KnowledgeEngine (Step 5)
  ├── "planner"                   ─── PlannerEngine alias (Step 6)
  ├── "desktop_controller"        ─── DesktopController (Step 7, from core.dependencies)
  ├── "tool_registry"             ─── ToolRegistry (Step 7, from core.dependencies)
  ├── "desktop_automation"        ─── DesktopAutomationService (Step 7b)
  ├── "tool_engine"               ─── ToolEngine (Step 7c)
  ├── "telemetry"                 ─── MissionTelemetry (Step 8)
  ├── "mission_engine"            ─── MissionManager (Step 8)
  ├── "workflow_history"          ─── WorkflowHistory (Step 9)
  ├── "workflow_engine"           ─── WorkflowEngine (Step 9)
  ├── "scheduler"                 ─── OrionScheduler (Step 10)
  ├── "llm_router"                ─── LLMRouter (Step 10b)
  ├── "agent_message_bus"         ─── AgentMessageBus (Step 11)
  ├── "agent_registry"            ─── AgentRegistry (Step 11)
  ├── "agent_scheduler"           ─── AgentScheduler (Step 11)
  ├── "agent_telemetry"           ─── AgentTelemetry (Step 11)
  ├── "shared_context"            ─── SharedContext (Step 11)
  ├── "agent_coordinator"         ─── AgentCoordinator (Step 11)
  ├── "workflow_persistence"      ─── WorkflowPersistence (Step 12)
  ├── "checkpoint_manager"        ─── CheckpointManager (Step 12)
  ├── "workflow_worker_agent"     ─── WorkflowWorkerAgent (Step 12)
  ├── "workflow_runtime_executor"─── WorkflowRuntimeExecutor (Step 12)
  ├── "workflow_runtime_manager"  ─── WorkflowRuntimeManager (Step 12)
  └── "runtime_scheduler_bridge"  ─── RuntimeSchedulerBridge (Step 12)
```

**22 registered services.** All properly instantiated in boot order. No circular dependencies identified (topological sort succeeds). No duplicate registrations.

---

## 6. Event Flow Graph

```
Published Event Topics           Subscribers
═══════════════════              ═══════════════════════════════════

ConversationReceived             → PlannerEngine
MemoryRetrieved                  → PlannerEngine
PlanValidated                    → ToolEngine (stub handler)
ToolCompleted                    → KnowledgeEngine, MemoryManager, PlannerEngine
MissionStarted                   → ToolEngine (stub handler)
MissionCompleted                 → KnowledgeEngine, MemoryManager, PlannerEngine
MissionUpdated                   → (none beyond API publish)
MissionCancelled                 → (none beyond API publish)
WorkflowStarted                  → ToolEngine (stub handler)
WorkflowCompleted                → KnowledgeEngine, MemoryManager, PlannerEngine
MemoryUpdated                    → ToolEngine (stub handler), KnowledgeEngine
ConversationCompleted            → MemoryManager
SessionSummarized                → (test only)
DocumentIndexed                  → (test only)
EmbeddingGenerated               → (test only)
KnowledgeRetrieved               → (test only)
IntentDetected                   → (test only)
PlanCreated                      → (test only)
AgentTaskCreated                 → (subscriber unknown)
AgentTaskStarted                 → (subscriber unknown)
AgentTaskCompleted               → (subscriber unknown)
AgentTaskFailed                  → (subscriber unknown)
AgentCircuitBreakerTripped       → (subscriber unknown)
AgentDeadLetterMessage           → (subscriber unknown)
KernelBooting                    → (test only)
KernelReady                      → (test only)
KernelShutdown                   → (test only)
KernelRestart                    → (test only)
KernelError                      → (test only)
TelemetryUpdated                 → stream.py (WebSocket)
KernelHealthChanged              → stream.py (WebSocket)
ServiceStatusChanged             → stream.py (WebSocket)
```

**Key findings:**
- 11 event topics are published but have zero production subscribers (only test subscribers).
- Workflow Runtime events (`WorkflowStarted`, `WorkflowStepStarted`, `WorkflowStepCompleted`, `WorkflowPaused`, `WorkflowResumed`, `WorkflowFailed`, `WorkflowCompleted`, `WorkflowCancelled`) are **all published but never subscribed to** by any production code.
- ToolEngine's 4 event handlers are stubs that only log.
- MemoryManager is the best subscriber — it actually processes `ConversationCompleted`, `ToolCompleted`, `MissionCompleted` events.

---

## 7. Startup Sequence

```
Step  1: Load Configuration (from OrionKernelConfig)
Step  2: Initialize Logger (loguru)

  Phase 1: Core Infrastructure
Step  3: EventBus (DI: "event_bus")
Step  4: MemoryEngine (DI: "memory_engine" — from core.dependencies)

  Phase 2: Intelligence Layer
Step  5: KnowledgeEngine (DI: "knowledge_engine")
Step  6: PlannerEngine (DI: "planner" — alias for PlannerEngine)

  Phase 3: Desktop & Tools
Step  7: DesktopController + ToolRegistry (DI: from core.dependencies)
Step 7b: DesktopAutomationService (DI: "desktop_automation" — await initialize())
Step 7c: ToolEngine (DI: "tool_engine")

  Phase 4: Execution & Scheduling
Step  8: MissionEngine (DI: "mission_engine", "telemetry" — MissionManager)
Step  9: WorkflowEngine (DI: "workflow_engine", "workflow_history")
Step 10: OrionScheduler (DI: "scheduler" — PLACEHOLDER)
Step 10b: LLMRouter + GeminiAdapter (DI: "llm_router")
          Late-bind LLMRouter → WorkflowEngine._llm_router

  Phase 5: Multi-Agent Runtime (Alpha 4.5)
Step 11: AgentMessageBus → AgentRegistry → AgentScheduler → AgentTelemetry
         → SharedContext → AgentCoordinator
         (AgentScheduler.start() called here)

  Phase 6: Workflow Runtime (Alpha 5.0)
Step 12: WorkflowPersistence → CheckpointManager → WorkflowWorkerAgent
         → WorkflowRuntimeExecutor → WorkflowRuntimeManager → RuntimeSchedulerBridge
         (WorkflowWorkerAgent registered with AgentRegistry)

Post-Boot: OrionKernel.boot()
  ├── LifecycleManager.initialize_all() — calls initialize() on every module
  ├── LifecycleManager.start_all() — calls start() on every module
  └── KernelReady event published
```

---

## 8. Shutdown Sequence

```
OrionKernel.shutdown()
  │
  ├── Publish KernelShutdown event (fire-and-forget)
  │
  ├── LifecycleManager.shutdown_all()
  │     └── Topological reverse order:
  │         scheduler → llm_router → workflow_engine → mission_engine
  │         → tool_engine → desktop_automation → desktop_controller
  │         → planner → knowledge_engine → memory_engine → event_bus
  │         [NOTE: agent_coordinator and workflow_runtime are NOT in
  │          topological_sort() because their dependencies (event_bus,
  │          memory_engine, knowledge_engine, planner) exist but the
  │          modules themselves may not have shutdown() hooks registered]
  │
  ├── Iterate all services → unregister_service() for each
  │     └── Publishes ServiceStopped event (fire-and-forget)
  │
  └── Set state to STOPPED
```

**Issues:**
- `agent_coordinator` module was registered with deps `["event_bus", "memory_engine", "knowledge_engine", "planner"]` but `AgentCoordinator` may not have a `shutdown()` or `stop()` method that the lifecycle manager can call.
- `workflow_runtime` module similarly may not have lifecycle hooks that are called.
- Fire-and-forget tasks from `_publish_event()` are not awaited during shutdown — events may be lost.
- No graceful AgentScheduler tick loop cancellation before module shutdown (the `AgentScheduler.start()` loop task is orphaned if shutdown is called).

---

## 9. Subsystems Implemented but Never Used

| Subsystem | Status | Evidence |
|-----------|--------|----------|
| **WorkflowRuntime** | ✅ Implemented, ❌ Never used | No API endpoints, no orchestrator integration, no event subscribers for its events |
| **RuntimeSchedulerBridge** | ✅ Implemented, ❌ Never called | `submit_plan()` and `schedule_plan()` never invoked |
| **WorkflowWorkerAgent** | ✅ Registered in kernel, ❌ Never tasked | No code path creates `AgentTask` with `step_type` matching its capabilities |
| **CheckpointManager** | ✅ Implemented, ❌ Never used | `executor._checkpoints.save_checkpoint()` called during step execution, but the workflow runtime is never started |
| **WorkflowPersistence** | ✅ Implemented, ❌ Unreachable | Would persist workflows if runtime was started, but currently only stores data that no one reads |
| **AgentScheduler (cron)** | ✅ Implemented, ❌ No cron executed | `start()` is `pass` with TODO. `_tick_loop` exists but may not actively check schedules |
| **DeadLetterQueue** | ✅ Implemented, ❌ Never drained | `coordinator.delegate()` pushes to DLQ on failure, but no code calls `retry()` or `retry_all()` |
| **CircuitBreaker** | ✅ Implemented, ❌ Never inspected | Circuit states are tracked but no alerting or dashboard reads them |

---

## 10. Placeholders and TODOs

### Source files with TODO comments:

| File | Line | Content |
|------|------|---------|
| `app/events/events.py` | 8 | `# TODO: Include serialized schemas / Validate event payload parameters` |
| `app/scheduler/triggers.py` | 13 | `# TODO: Compute trigger matching logic` |
| `app/scheduler/scheduler.py` | 20 | `# TODO: Launch asynchronous schedule check thread` |
| `app/scheduler/scheduler.py` | 36 | `# TODO: Safely join threads and cleanup` |
| `app/kernel/boot.py` | 188 | `logger.info("Boot Step 10: Initialize Scheduler (Placeholder)...")` |
| `app/policies/confirmation.py` | 27 | `# TODO: Implement confirmation checking rules` |
| `app/policies/safety.py` | 24 | `# TODO: Implement safety check rules` |
| `app/policies/permissions.py` | 25 | `# TODO: Implement database lookup permissions` |
| `app/workflow/workflow_store.py` | 24 | `# TODO: Implement persistence serializations` |
| `app/workflow/workflow_store.py` | 37 | `# TODO: Implement database search query loops` |
| `app/workflow/workflow_engine.py` | 28 | `# TODO: Implement full execution loop coordination` |
| `app/workflow/workflow_runner.py` | 30 | `# TODO: Implement step capability mapping and execution` |
| `app/workflow/workflow_state.py` | 15 | `# TODO` (empty stub) |
| `app/orion/knowledge_embeddings.py` | 26 | `Placeholder class for future OpenAI embedding...` |
| `app/capabilities/registry.py` | 23 | `# TODO: Handle name collisions and logging` |
| `app/scheduler/jobs.py` | 8 | `# TODO` (empty stub) |

### Files with `pass` as method body (placeholder implementations):

| File | Methods with `pass` |
|------|---------------------|
| `app/workflow/workflow_store.py` | `save()`, `load()` |
| `app/workflow/workflow_runner.py` | `_execute_step()` |
| `app/workflow/workflow_engine.py` | `_execute_workflow()` (stub) |
| `app/scheduler/scheduler.py` | `start()`, `stop()` |
| `app/scheduler/triggers.py` | `match()` |
| `app/policies/confirmation.py` | `require_confirmation()`, `check_confirmation()` |
| `app/policies/safety.py` | `check_safety()` |
| `app/policies/permissions.py` | `check_permission()` |
| `app/orion/vectordb.py` | `query()`, `upsert()`, `delete()` all `pass` |
| `app/orion/knowledge_embeddings.py` | `generate_embeddings()` is `pass` |
| `app/orion/tool_sandbox.py` | `validate()` is `pass` |
| `app/desktop/controller.py` | Multiple methods with `pass` (stub implementations) |
| `app/desktop/automation.py` | `_execute_browser_action()`, `_execute_form_fill()` |
| `app/desktop/launcher.py` | `launch()` |
| `app/desktop/process_manager.py` | `list_processes()`, `kill_process()`, `get_process_info()` |
| `app/desktop/clipboard.py` | Multiple methods with `pass` |
| `app/desktop/window_manager.py` | `list_windows()` |
| `app/desktop/screenshot.py` | Multiple methods with `pass` |
| `app/desktop/notifications.py` | `send()`, `listen()` |
| `app/llm/base.py` | `generate()`, `generate_stream()` |
| `app/memory/store.py` | 7 stub methods |
| `app/kernel/plugin_api.py` | 8 stub methods |
| `app/kernel/errors.py` | 7 stub exception classes |
| `app/api/stream.py` | Multiple SSE/WebSocket stub handlers |
| `app/capabilities/capability.py` | 6 stub methods |

**Total: ~90 `pass` statements across 25+ files.**

---

## 11. Prioritized Implementation Roadmap

### Must Fix (Critical — blocks Alpha 5.0 from being usable)

```
1. [C1] Adapter: ExecutionPlan → ExecutionPlanInput
   - Create adapter function in app/workflow_runtime/ that converts
     Planner's ExecutionPlan to WorkflowRuntime's ExecutionPlanInput
   - Set plan_id from UUID, variables from ExecutionPlan fields,
     metadata from capabilities/priority/confidence
   - Effort: ~15 lines + test

2. [C2] API routes for Workflow Runtime
   - Add router in app/api/workflow_runtime.py (or extend existing)
   - Endpoints: POST /runtime/plans (submit plan), POST /runtime/workflows,
     GET /runtime/workflows, GET /runtime/workflows/{id},
     POST /runtime/workflows/{id}/pause, POST /runtime/workflows/{id}/resume,
     POST /runtime/workflows/{id}/cancel, POST /runtime/workflows/{id}/retry
   - Wire RuntimeSchedulerBridge into the route handlers
   - Effort: ~200 lines + tests

3. [C3] Connect Orchestrator → Workflow Runtime
   - In app/orion/orchestrator.py process_query(): after Planner produces
     ExecutionPlan, convert to ExecutionPlanInput and submit via
     RuntimeSchedulerBridge to the workflow runtime
   - Option: add runtime as an optional code path behind a feature flag
   - Effort: ~30 lines
```

### Should Fix (High — structural issues)

```
4. [H1] Implement OrionScheduler
   - Replace pass stubs in start()/stop()
   - Implement tick loop (app/scheduler/scheduler.py already has
     _tick_cycle pattern from AgentScheduler, replicate it)
   - Effort: ~80 lines

5. [H5/H6] Add workflow_runtime to KernelHealth
   - Add "workflow_runtime" field to KernelHealth Pydantic model
   - Add health check call in kernel.health() method
   - Wire RuntimeSchedulerBridge.health() into the aggregation
   - Effort: ~20 lines

6. [H4] Fix fire-and-forget event tasks
   - Add tracked_tasks set to OrionKernel or service base class
   - Replace all loop.create_task() with tracked version
   - Cancel all tracked tasks in shutdown()
   - Effort: ~50 lines across 4 files

7. [H3] Consolidate capability registries
   - Merge app/capabilities/ (ABC) and app/orion/capability_registry.py
     (Pydantic) into app/kernel/capability.py (OrionCapabilityRegistry)
   - Create migration paths for all consumers
   - Effort: ~100 lines + test updates
```

### Nice to Fix (Medium — robustness)

```
8. [M5] Prevent double _run_workflow invocation
   - Guard resume() and retry_step() with task-done check
   - Effort: ~10 lines

9. [M6] Fix JSON serialization for datetime timezone
   - Use mode="python" + custom serializer, or ensure
     datetime objects are timezone-naive for JSON dump
   - Effort: ~5 lines

10. [M8] Unsubscribe event handlers on shutdown
    - Add subscribe/unsubscribe tracking in EventBus
    - Call unsubscribe from each service shutdown() method
    - Effort: ~40 lines + updates to each subscriber

11. [M4] Wire WorkflowWorkerAgent into a real task path
    - Ensure that when workflow runtime starts, AgentTask
      objects route to the workflow-worker agent
    - Currently executor.py creates tasks with type=step_type,
      which should match workflow-worker's capabilities
    - Effort: verify existing wiring works when connected
```

### Polish (Low — tech debt)

```
12. [L1] Extract service name constants
    - Create ServiceNames enum or frozen class
    - Replace 30+ string literals in boot.py
    - Effort: ~40 lines

13. [L2] Read workspace_root from kernel config
    - Replace hardcoded path in core/dependencies.py
    - Effort: ~5 lines

14. [L3] Cache SharedContext property lookups
    - Resolve kernel services once in constructor
    - Effort: ~15 lines

15. [L4] Implement or remove policies subsystem
    - Either implement confirmation/permission/safety logic
      or extract the stubs into a separate package
    - Effort: varies
```

---

## Summary

| Metric | Count |
|--------|-------|
| Subsystems wired into kernel | 13 of 13 |
| Subsystems reachable via API | 7 of 13 |
| Subsystems called from request path | 5 of 13 |
| Critical blockers for Alpha 5.0 | 3 |
| High-severity issues | 4 |
| Medium-severity issues | 5 |
| Low-severity issues | 5 |
| TODO comments in source | 31 |
| `pass` placeholders | ~90 |
| Fire-and-forget orphaned tasks | 4 |
| Parallel capability registries | 3 |
| Event topics with zero subscribers | 11 |
| Tests passing | 157 / 157 |

**Bottom line:** Alpha 5.0 Workflow Runtime is correctly implemented and tested in isolation, but is **not connected** to the running system. The three critical items (adapter, API routes, orchestrator integration) must be completed before the runtime can process a single user request.
