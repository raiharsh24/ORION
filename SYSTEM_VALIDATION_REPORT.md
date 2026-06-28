# FRIDAY System Validation Report

**Date:** 2026-06-28
**Scope:** Full-stack static analysis — Desktop UI → Express Gateway → Friday API (Node.js + Python)
**Validator:** Lead Software Architect

---

## 1. Architecture Overview

```
Desktop UI (Vite, port 5173)
  │
  ├─ fetch("http://localhost:5000/chat") ──→ Express Gateway (port 5000)
  │                                              │
  │                                              ├─ POST /chat    → Node.js FridayEngine → GeminiProvider → ResponseFormatter
  │                                              ├─ POST /ask     → http-proxy-middleware → Python FastAPI (port 8000)
  │                                              ├─ POST /chat/stream → Node.js streaming → SSE
  │                                              └─ GET /events   → proxy → Python SSE
  │
  └─ WebSocket("ws://localhost:5000/ws") ──→ Gateway → proxy → Python WebSocket
```

Two entirely independent conversation stacks exist:

| Layer | Path A (Node.js) | Path B (Python) |
|-------|------------------|-----------------|
| Entry | POST /chat | POST /ask, POST /chat |
| Engine | FridayEngine.js | FridayOrchestrator (Python) |
| Session | SessionManager (in-memory) | ConversationMemory (in-memory dict) |
| LLM | GeminiProvider | LLMRouter → GeminiAdapter |
| Stream | StreamManager (SSE chunks) | process_stream() → SSE `data:` |
| State | Node.js heap | Python process dict |

---

## 2. Execution Sequence Diagram

### Path A: Desktop → Node.js Chat (non-stream)

```
Desktop                 Gateway                 FridayEngine              SessionManager          GeminiProvider
  │                        │                        │                        │                       │
  │─ POST /chat ──────────→│                        │                        │                       │
  │  {prompt, session_id}  │                        │                        │                       │
  │                        │─ engine.chat() ───────→│                        │                       │
  │                        │                        │─ getOrCreate() ───────→│                       │
  │                        │                        │←─ session ────────────│                       │
  │                        │                        │─ buildContext() ──────→│                       │
  │                        │                        │←─ context ────────────│                       │
  │                        │                        │─ buildPrompt()         │                       │
  │                        │                        │─ generate() ──────────────────────────────────→│
  │                        │                        │←─ response ───────────────────────────────────│
  │                        │                        │─ formatResponse()      │                       │
  │                        │                        │─ updateSession() ─────→│                       │
  │                        │←─ {success,response} ─│                        │                       │
  │←─ 200 JSON ───────────│                        │                        │                       │
  │                        │                        │                        │                       │
```

### Path B: Direct Python Chat (non-stream)

```
Client                  FastAPI                 FridayOrchestrator       IntentClassifier        Planner
  │                        │                        │                        │                   │
  │─ POST /ask ───────────→│                        │                        │                   │
  │                        │─ process_query() ─────→│                        │                   │
  │                        │                        │─ classify() ──────────→│                   │
  │                        │                        │←─ intent ─────────────│                   │
  │                        │                        │─ plan() ──────────────────────────────────→│
  │                        │                        │←─ plan ───────────────────────────────────│
  │                        │                        │                        │                   │
  │                        │                        │─ [if plan] execute()                        │
  │                        │                        │   → ToolExecutor / RuntimeBridge            │
  │                        │                        │                        │                   │
  │                        │                        │─ memory.add_message()  │                   │
  │                        │                        │─ prompt.format()       │                   │
  │                        │                        │─ llm.generate()        │                   │
  │                        │                        │─ memory.add_message()  │                   │
  │                        │                        │─ calculate_telemetry() │                   │
  │                        │←─ FridayResponse ──────│                        │                   │
  │←─ AskResponse ────────│                        │                        │                   │
```

### Path C: Streaming (Desktop → Node.js → SSE → Desktop)

```
Desktop              Gateway                  FridayEngine              GeminiProvider
  │                     │                         │                       │
  │─ POST /chat ───────→│                         │                       │
  │ stream:true         │                         │                       │
  │                     │─ engine.streamChat() ──→│                       │
  │                     │                         │─ generateStream() ───→│
  │                     │  streamSource {          │                       │
  │                     │    on('data') ───────────│←─ chunk ─────────────│
  │data: {chunk} ──────│   onChunk()              │                       │
  │                     │  }                       │                       │
  │                     │                         │←─ chunk ─────────────│
  │data: {chunk} ──────│   onChunk()              │                       │
  │                     │                         │←─ [DONE] ────────────│
  │data: {done:true} ──│   onComplete()           │                       │
  │                     │                         │                       │
  │─ GET /sessions/:id →│                         │                       │
  │←─ telemetry ───────│                         │                       │
```

---

## 3. Runtime Call Graph

### All entry points → leaf dependencies

```
POST /chat (Gateway)  ──→ chatController.js
  ├─ engine.chat() ──────→ FridayEngine.js
  │   ├─ SessionManager.getOrCreateSession()
  │   ├─ ConversationManager.getHistory()
  │   ├─ ContextManager.build()
  │   ├─ PromptBuilder.build()
  │   ├─ ProviderFactory.getProvider() → GeminiProvider.generate()
  │   ├─ ResponseFormatter.format()
  │   └─ SessionManager.updateSession()
  │
  ├─ engine.streamChat() → FridayEngine.js
  │   ├─ (same path but stream: true)
  │   └─ StreamManager.handleStream()
  │       ├─ onChunk → res.write(`data: ...\n\n`)
  │       ├─ onComplete → res.write(`data: [DONE]\n\n`); res.end()
  │       └─ onError → res.write(`data: {error}\n\n`); res.end()

POST /ask (Gateway proxy → Python)  ──→ routes.py:ask()
  ├─ get_orchestrator() → FridayKernel.boot()
  │   └─ BootManager.run_boot_sequence()
  │       ├─ EventBus
  │       ├─ MemoryEngine → MemoryManager → JSONStore/InMemoryStore
  │       ├─ KnowledgeEngine
  │       ├─ Planner
  │       ├─ DesktopController + ToolRegistry
  │       ├─ ToolEngine
  │       ├─ MissionEngine
  │       ├─ WorkflowEngine
  │       ├─ LLMRouter → GeminiAdapter
  │       ├─ AgentCoordinator + AgentRegistry + AgentScheduler
  │       └─ WorkflowRuntimeExecutor + WorkflowRuntimeManager + RuntimeSchedulerBridge
  │
  └─ orchestrator.process_query()
      ├─ IntentClassifier.classify()
      ├─ Planner.plan()
      │   └─ ToolExecutor.execute() OR RuntimeBridge.submit_and_wait()
      │       └─ WorkflowRuntimeExecutor.execute_step()
      │           └─ AgentCoordinator.delegate() → WorkflowWorkerAgent.execute_task()
      ├─ ConversationMemory.add_message()
      ├─ PromptManager.format_prompt()
      ├─ LLMRouter.generate() → GeminiAdapter.generate()
      ├─ ConversationMemory.add_message()
      └─ Response calculation

POST /chat/stream (Gateway)  ──→ streamChatController.js
  └─ (same as chatController stream branch)

GET /events (Gateway proxy → Python) → Python SSE stream
GET /ws (Gateway proxy → Python) → Python WebSocket
```

---

## 4. Event Flow Graph

```
EventBus (singleton, in-process)
  │
  ├─ subscribe("ConversationCompleted", MemoryManager.on_conversation_completed)
  ├─ subscribe("ToolCompleted",          MemoryManager.on_tool_completed)
  ├─ subscribe("MissionCompleted",       MemoryManager.on_mission_completed)
  ├─ subscribe("WorkflowCompleted",      MemoryManager.on_workflow_completed)
  │
  ├─ ← AgentCoordinator publishes:
  │   AgentTaskCreated, AgentTaskStarted, AgentTaskCompleted,
  │   AgentTaskFailed, AgentTaskCancelled, AgentTaskTimeout
  │
  ├─ ← BaseAgent publishes:
  │   AgentStatusChanged, AgentTaskStarted, AgentTaskCompleted,
  │   AgentTaskFailed, AgentTaskCancelled, AgentTaskTimeout,
  │   AgentMessageSent, AgentMessageReceived, AgentError
  │
  ├─ ← AgentRegistry publishes:
  │   AgentRegistered, AgentUnregistered
  │
  ├─ ← WorkflowRuntimeExecutor publishes:
  │   WorkflowStepStarted, WorkflowStepCompleted
  │
  └─ ← FridayKernel publishes:
      KernelBooting, KernelReady, KernelShutdown, KernelRestart,
      KernelError, ServiceRegistered, ServiceStopped, ServiceFailed

Desktop StreamManager (client-side, 3-transport fallback)
  ├─ WebSocket → topic-based SystemEvent dispatch
  ├─ SSE → per-topic EventSource listeners
  └─ Polling (no-op, page drives)

Key gap: No component subscribes to KernelShutdown to perform cleanup.
Key gap: EventBus has no unsubscribe calls anywhere.
```

---

## 5. Data Flow Graph

### Variable propagation through the Python path:

```
Request body (prompt, session_id, stream, confirmed, confirmation_token)
  │
  ▼
routes.py → AskRequest.session_id
  │                                                              [JSONStore]
  │  ┌──────────────────────────────────────────────────────┐  session:xxx → {messages, context}
  │  │  MemoryEngine                                        │  project:xxx → {name, path, ...}
  │  │    ├─ MemoryManager                                  │  conversation:xxx → [...]
  │  │    │   ├─ MemoryStore (InMemoryStore / JSONStore)     │  working:xxx → {key: value}
  │  │    │   └─ MemorySerializer                            │
  │  │    └─ ConversationMemory (separate dict!)             │  [ConversationMemory dict]
  │  │       ChatSession: {messages[], summary, context}     │  session_id → ChatSession
  │  └──────────────────────────────────────────────────────┘
  │
  ▼
FridayOrchestrator.process_query()
  ├─ Intent: "SYSTEM_COMMAND" | "CHAT" | "WORKFLOW" | ...
  ├─ Plan: {tool_name, steps[], variables{}}
  │   └─ ToolExecutor.execute() → ToolOutput
  │   └─ OR RuntimeBridge.submit_and_wait()
  │       └─ RuntimeWorkflow.variables (shared mutable dict!)
  │           └─ execute_parallel_steps: concurrent writes to same dict
  ├─ FullPrompt: system_instruction + history + user_message + tool_output
  ├─ LLM Response: str
  └─ FridayResponse: {success, intent, response, tool_used, session_id, execution_time_ms, telemetry}
  │
  ▼
AskResponse / AskResponse (via route)
  └─ Desktop reads: response, intent, tool_used, execution_time_ms, telemetry
     └─ Falls back to fake telemetry if not present:
        prompt.length/4, accumulated.length/4, 150+Math.random()*90
```

### Variable propagation through the Node.js path:

```
Request body (prompt, session_id, stream)
  │
  ▼
FridayEngine.chat()
  ├─ SessionManager.getOrCreateSession(sessionId) → ChatSession
  ├─ ConversationManager.getHistory(sessionId) → messages[]
  ├─ ContextManager.build(sessionId, message) → {sessionContext, ...}
  ├─ PromptBuilder.build() → prompt string
  ├─ GeminiProvider.generate(prompt) → response text
  ├─ ResponseFormatter.format(response) → {success, provider, model, response, usage, metadata}
  └─ SessionManager.updateSession(sessionId, ...)
  │
  ▼
← 200 JSON {success, provider, model, response, usage, metadata}
  └─ Desktop reads: response
```

---

## 6. Dependency Graph

```
FridayKernel (singleton)
  ├── FridayServiceContainer (DI)
  │   ├── event_bus (EventBus)
  │   ├── memory_engine (MemoryEngine → MemoryManager → JSONStore)
  │   ├── knowledge_engine (KnowledgeEngine)
  │   ├── planner (Planner)
  │   ├── desktop_controller (DesktopController)
  │   ├── tool_registry (ToolRegistry)
  │   ├── desktop_automation (DesktopAutomationService)
  │   ├── tool_engine (ToolEngine)
  │   ├── telemetry (MissionTelemetry)
  │   ├── mission_engine (MissionManager)
  │   ├── workflow_history (WorkflowHistory)
  │   ├── workflow_engine (WorkflowEngine)
  │   ├── scheduler (FridayScheduler)
  │   ├── llm_router (LLMRouter → GeminiAdapter)
  │   ├── agent_message_bus (AgentMessageBus → EventBus)
  │   ├── agent_registry (AgentRegistry → EventBus + MessageBus)
  │   ├── agent_scheduler (AgentScheduler → EventBus)
  │   ├── agent_telemetry (AgentTelemetry → EventBus)
  │   ├── shared_context (SharedContext → kernel + event_bus)
  │   ├── agent_coordinator (AgentCoordinator → registry + bus + scheduler + telemetry + context + event_bus)
  │   ├── workflow_persistence (WorkflowPersistence)
  │   ├── checkpoint_manager (CheckpointManager)
  │   ├── workflow_worker_agent (WorkflowWorkerAgent → registered in AgentRegistry)
  │   ├── workflow_runtime_executor (WorkflowRuntimeExecutor → coordinator + context + checkpoints + event_bus)
  │   ├── workflow_runtime_manager (WorkflowRuntimeManager → persistence + executor + event_bus)
  │   └── runtime_scheduler_bridge (RuntimeSchedulerBridge → manager + agent_scheduler)
  │
  ├── FridayModuleRegistry (module → dependencies + instance)
  ├── FridayCapabilityRegistry (name → module → description)
  ├── FridayLifecycleManager (module_registry → topological init/start/shutdown)
  ├── FridayHealthMonitor (health checks)
  ├── FridayConfigSystem (config)
  └── FridayKernelContext (user + mission + workspace + services + state + config + metadata)
```

---

## 7. Complete Issue Inventory

### CRITICAL (3)

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| **C1** | **WorkflowWorkerAgent has no context — every step execution crashes** | `worker_agent.py:55-58`, `registry.py:15-30`, `boot.py:285-290` | `AgentRegistry.register()` calls `agent.set_event_bus()` and `agent.set_message_bus()` but **never calls `agent.set_context()`**. The `WorkflowWorkerAgent._execute_tool()`, `_execute_llm()`, `_execute_knowledge()`, `_execute_mission()`, `_execute_notification()`, and `_execute_agent_task()` all read `self._context` (inherited from `BaseAgent`, initialized to `None`). The agent stores its own `self._shared_context` (passed at construction) but never uses it. Every tool/LLM/knowledge/mission/notification execution raises `RuntimeError("SharedContext unavailable for ...")`. The full Workflow Runtime pipeline — `Orchestrator → RuntimeBridge → WorkflowRuntimeExecutor → AgentCoordinator → WorkflowWorkerAgent` — cannot execute any step. |
| **C2** | **EventBus subscribers never unsubscribe — memory leak on restart** | `engine.py:43-46`, `bus.py:23-37` | `MemoryEngine.initialize()` subscribes 4 callbacks to EventBus: `ConversationCompleted`, `ToolCompleted`, `MissionCompleted`, `WorkflowCompleted`. Neither `MemoryEngine.shutdown()` nor `EventBus` has an unsubscribe mechanism integrated — no component tracks subscription handles for cleanup. On every `FridayKernel.restart()` or `shutdown()/boot()` cycle (which the health endpoint triggers if state != READY), 4 new subscriber entries are appended. After N restarts, N×4 handlers dispatch for every matched event, causing duplicate side effects. |
| **C3** | **AgentCoordinator has no shutdown lifecycle — tasks, circuit breakers, dead letter queue leak** | `coordinator.py:40-44`, `kernel.py:133-161` | `AgentCoordinator` initializes `_pending_tasks`, `_active_delegations`, `_circuit_breakers`, and `_dead_letter_queue` in `__init__` but provides **no `shutdown()` method**. `FridayKernel.shutdown()` calls `LifecycleManager.shutdown_all()` which iterates registered modules — but `agent_coordinator` is registered as a module with dependencies, and its instance **has no `shutdown`, `stop`, or `close` method**. All pending tasks, circuit breaker state, and queued dead letters are orphaned on kernel shutdown/restart. The `AgentScheduler` started in boot step 11 also has no registered shutdown. |

### HIGH (7)

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| **H1** | **Two independent session stores with zero synchronization** | `conversation.py:23-24` (Python dict), SessionManager.js (Node.js in-memory) | Python's `ConversationMemory._sessions` is a plain dict holding `ChatSession` objects; Node.js's `SessionManager` is an in-memory Map. They share the same `session_id` namespace but have **no data consistency mechanism**. The Desktop calls `POST /chat` → Node.js path, which stores session in Node.js memory. The Python `/ask` path stores in Python memory. `GET /sessions/:id` returns Node.js session data; Python's ConversationMemory is never queried. Sessions created in one path are invisible to the other. |
| **H2** | **Duplicate model definitions across subsystems** | Multiple files | `ChatMessage` is defined in both `conversation.py:5-8` and `schema.py:5-8`. `ToolExecutionResult` is defined in `executor.py` and `tool_engine.py`. `CapabilityRegistry` exists in both `friday/` and `kernel/`. `PermissionManager` in `policies/` and `tool_permission/`. These are structurally identical but independent — no shared base class, no validation that they stay in sync. |
| **H3** | **Sequential event dispatch — no concurrent fan-out, subscriber chain blocks publisher** | `bus.py:84-92` | `EventBus.publish()` collects all matching subscribers, sorts by priority, then **dispatches sequentially in the publisher's coroutine**. A slow subscriber (e.g., `MemoryManager.on_conversation_completed` doing full JSON serialization) blocks all subsequent subscribers and the caller's event loop. There is no `asyncio.gather()` or `create_task()` fan-out for independent handlers. |
| **H4** | **Fire-and-forget event publishing — background tasks fail silently** | `coordinator.py:219-233`, `base.py:95-110`, `registry.py:81-96`, `executor.py:168-178` | Four components use identical pattern: `loop.create_task(self._event_bus.publish(event))` with bare `except Exception: logger.error(...)`. The `create_task` firehose means: (a) tasks are uncancellable, (b) exceptions after the `create_task` call are caught only by the generic logger.error inside the publish call, (c) if the event loop is closed during shutdown, `create_task` raises `RuntimeError` which is suppressed, and (d) no backpressure mechanism exists for a backed-up subscriber chain. |
| **H5** | **Concurrent write race in execute_parallel_steps on shared variables dict** | `executor.py:93-109`, `executor.py:67-68` | `execute_parallel_steps()` passes the shared mutable `variables` dict to every concurrent `execute_step()` call via `asyncio.gather()`. Each step's success handler does `variables.update({f"{step.step_id}.output": result})`. Multiple concurrent `.update()` calls race — one step's output may overwrite another's, or the dict may observe partial updates mid-iteration from `_resolve_variables`. |
| **H6** | **Desktop telemetry fabricates fake data** | `useSystemStore.ts:396-408` | After a streaming response completes, the Desktop queries `GET /sessions/:id` but overrides the returned data with **fake telemetry**: execution time is `150 + Math.random() * 90`, token counts are `prompt.length / 4` and `accumulated.length / 4`. The model is hardcoded as `'gemini-1.5-flash'`. The real telemetry from the backend is discarded. |
| **H7** | **No cancellation propagation — Desktop abort does not reach LLM provider** | `chatController.js:36-39`, `engine.js` | The Gateway creates an `AbortController` and passes `signal` to `engine.streamChat()`, but the Node.js `GeminiProvider` and Python `GeminiAdapter` both **read the entire response before yielding**. The abort signal only stops writing to the HTTP response — the LLM API call continues to completion server-side, wasting quota and latency. On the Python side, streaming cancellation is entirely absent; client disconnect leaves the generator running, accumulating an unbounded response. |

### MEDIUM (10)

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| M1 | No request timeout for Python path — `asyncio.wait_for` only in agent tasks | `routes.py:36-69`, `orchestrator.py` | The `/ask` and `/chat` FastAPI routes have no timeout. The orchestrator can block indefinitely on LLM calls. Timeout exists only in `BaseAgent.process_task()` for agent subtasks. |
| M2 | Inconsistent field naming: `sessionId` vs `session_id`, `message` vs `prompt` | `chatController.js:17-18`, `useSystemStore.ts:226-232`, `routes.py` | Gateway normalizes both, but Python routes only accept `prompt` and `session_id`. `AskRequest` and `ChatRequest` use different field names than the Node.js path. |
| M3 | Health endpoint returns hardcoded values | `routes/index.js:30-36,38-43,45-50` | `GET /knowledge/index` returns hardcoded `{indexed_chunks: 18}`. `GET /search` and `GET /knowledge/search` return hardcoded `{results: []}`. |
| M4 | Boot-time EventBus injection race | `kernel.py:190-193` | When `event_bus` is registered in `register_service()`, it flushes `_local_subscribers`. But `boot.py` Step 3 creates `EventBus` and calls `register_singleton()` directly (bypassing `register_service`), so the flush may not fire. Future `kernel.subscribe()` calls add to both local subscribers and EventBus — double delivery on Kernel.publish(). |
| M5 | `MemoryManager` serializes full session on every `add_message()` | `manager.py` | Every call to `add_message()` triggers `MemorySerializer.serialize_session()` which iterates all messages in the session, creates a full serialization dict, and stores it. For sessions with thousands of messages, this is O(n²) write cost. |
| M6 | No memory compaction or TTL for JSONStore | `store.py:68-109` | `JSONStore.load()` reads entire file into memory on init. `save()` writes entire dict to disk. No incremental persistence, no compaction, no TTL/eviction. A session with 100K messages loads/saves the entire dataset every write. |
| M7 | Agent discovery fallback bypasses capability filter | `coordinator.py:51-53` | `route_task()` first tries `discover(capability=task.type)`. If empty, it falls back to `discover()` (all agents). Any agent can receive any task type regardless of capability, defeating capability-based routing. |
| M8 | `MemoryEngine.shutdown()` only saves if store has `save()` method — no flush guarantee | `engine.py:56-61` | Shutdown checks `hasattr(self._manager._store, "save")` but `InMemoryStore.save()` is a no-op. Switching between JSONStore and InMemoryStore (based on config) changes durability behavior silently. |
| M9 | `DesktopAutomationService.initialize()` is awaited, but service has no shutdown | `boot.py:122-124`, `lifecycle_manager.py:95-126` | `DesktopAutomationService` is initialized (starts headless browser) but never shut down. On kernel restart, a new instance starts while the old browser process leaks. |
| M10 | `WorkflowRuntimeExecutor.build_from_plan()` silently ignores `parallel_group` | `executor.py:111-135` | `parallel_group` is parsed from step data but never used — `execute_parallel_steps()` is never called by any code path. Steps that could run in parallel are serialized. |

### LOW (8)

| # | Issue | File(s) | Description |
|---|-------|---------|-------------|
| L1 | `router.post("/chat")` on Python side exists but is never proxied by Gateway | `routes.py:71-113`, `app.js:60-66` | Python `/chat` is fully implemented (stream + non-stream, confirmation loop) but the Gateway does not proxy `/chat` to Python — it handles it via Node.js. Unused code. |
| L2 | `streamChatController` is functionally identical to `chatController` stream branch | `chatController.js:92-158` vs `chatController.js:35-67` | The stream branch of `chatController` and the separate `streamChatController` are identical except for validation order. Dead code path — no Desktop route calls `/chat/stream`. |
| L3 | `SharedContext` eager-initializes all services in constructor | `context.py:6-18` | Takes a `kernel` reference and immediately calls `kernel.get_service()` for 9 services in `__init__`. If any service is not yet registered, it silently becomes `None`. Defers errors to first use. |
| L4 | `FridayKernel.get_instance(config)` — config is ignored on subsequent calls | `kernel.py:57-61` | Singleton pattern: first call sets config, subsequent calls return the existing instance and silently discard the new config. |
| L5 | `Settings` import depends on local imports from `app.core.dependencies` | `routes.py:7`, `boot.py:67,110` | Mixed import styles: some imports are at module top, some are late inside functions. `routes.py` has `from app.core.dependencies import memory_store, tool_registry` at top but `get_orchestrator()` uses `kernel.boot()`. |
| L6 | `EventBus.add_middleware()` registered but never called by any code | `bus.py:16-21` | Middleware interceptors exist in the dispatch pipeline but no component calls `add_middleware()`. |
| L7 | `AgentCoordinator._publish_event()` creates task on event loop — no await | `coordinator.py:227` | Uses `loop.create_task()` for event publishing in a synchronous context. If the loop is closed, falls back to `asyncio.run()`. This can deadlock if called while a loop is already running in a different context. |
| L8 | `SystemContext` platform detection — no async initialization | `orchestrator.py:150` | `SystemContext()` is created synchronously in `process_query()` — platform detection uses `platform.system()` which blocks for ~100ms on some systems. Not cached — called on every request. |

---

## 8. Recommended Fixes

### Critical

**C1: Fix WorkflowWorkerAgent context** (`registry.py:15-30`, `boot.py:285-290`)
```python
# In AgentRegistry.register(), add:
agent.set_context(shared_context)  # shared_context must be passed to registry
# Or in boot.py, after register():
workflow_worker.set_context(shared_context)
```
Alternatively, in `worker_agent.py`, change all `self._context` references to `self._shared_context`.

**C2: Add unsubscribe on shutdown** (`engine.py:56-61`, `bus.py:39-44`)
```python
# MemoryEngine.shutdown():
self._event_bus.unsubscribe("ConversationCompleted", self._manager.on_conversation_completed)
# ... repeat for all 4 subscriptions
```
Return a token from `subscribe()` for scoped cleanup, or use weak references.

**C3: Add shutdown() to AgentCoordinator** (`coordinator.py`)
```python
async def shutdown(self) -> None:
    for task in self._pending_tasks.values():
        await self.cancel_task(task.task_id)
    self._pending_tasks.clear()
    for delegation in self._active_delegations.values():
        delegation.cancel()
    self._active_delegations.clear()
    self._circuit_breakers.clear()
    await self._dead_letter_queue.drain()
```
Register it as `shutdown` hook in the module registry.

### High

**H1: Unify session store or explicitly separate namespaces** — Option A: Route all session requests through Python (single source of truth). Option B: Add `path` prefix to session IDs (`node-{uuid}` vs `py-{uuid}`). Option C: Implement a session proxy that reads from both stores and merges.

**H2: Deduplicate models** — Move `ChatMessage`, `ToolExecutionResult`, `CapabilityRegistry`, `PermissionManager` into shared modules. Add `from app.models.shared import ChatMessage` in both conversation and schema modules.

**H3: Concurrent event fan-out** (`bus.py:84-92`)
```python
# Early-exit for independent handlers:
independent = [cb for cb, p in matching_handlers if p > 0]
dependent = [cb for cb, p in matching_handlers if p == 0]
results = await asyncio.gather(*[cb(current_event) for cb in independent], return_exceptions=True)
for cb in dependent:
    await cb(current_event)
```

**H4: Track background tasks for graceful cancellation** — Replace all `create_task()` patterns with a `BackgroundTaskManager` that stores `asyncio.Task` references and provides `cancel_all()` during shutdown.

**H5: Isolate step output variables per parallel branch** (`executor.py:93-109`)
```python
async def execute_parallel_steps(self, workflow, steps, variables):
    # Create per-step snapshot of variables to prevent race
    step_vars = [dict(variables) for _ in steps]
    coros = [self.execute_step(workflow, s, sv) for s, sv in zip(steps, step_vars)]
    results = await asyncio.gather(*coros, return_exceptions=True)
    # Merge outputs atomically
    for step, sv in zip(steps, step_vars):
        if f"{step.step_id}.output" in sv:
            variables[f"{step.step_id}.output"] = sv[f"{step.step_id}.output"]
```

**H6: Remove fake telemetry from Desktop** (`useSystemStore.ts:396-408`) — Either: (a) add `lastTelemetry` and `lastExecutionTimeMs` to the streaming response envelope, or (b) remove the fallback GET `/sessions/:id` and compute telemetry server-side, or (c) simply display "N/A" when telemetry is absent.

**H7: Propagate cancellation to LLM provider** — Pass `signal` parameter through `generate()` and `generate_stream()` to the underlying HTTP client. In Python, accept an `asyncio.Event` or `asyncio.CancelledError` and close the HTTP session.

### Medium

| # | Fix |
|---|-----|
| M1 | Add `asyncio.wait_for(process_query(), timeout=30)` in `/ask` and `/chat` handlers |
| M2 | Normalize field names in `AskRequest`/`ChatRequest` to accept both `sessionId`/`session_id` and `prompt`/`message` |
| M3 | Query actual KnowledgeEngine for chunk count; remove hardcoded endpoints or add deprecation notices |
| M4 | Remove `_local_subscribers` from Kernel; route all subscriptions through EventBus directly |
| M5 | Add incremental append to MemorySerializer — only write the new message, not the full session |
| M6 | Add periodic compaction (e.g., rewrite only dirty keys every N writes) and a TTL eviction policy |
| M7 | Remove fallback `discover()` — return error instead of routing to capability-mismatched agent |
| M8 | Add `flush()` method to `MemoryStore` base. `InMemoryStore.flush()` is no-op; `JSONStore.flush()` calls `save()`. |
| M9 | Add `DesktopAutomationService.shutdown()` that closes browser. Register it in the module registry. |
| M10 | Implement `execute_parallel_steps()` dispatch logic or remove dead `parallel_group` field from schema |

---

## 9. Summary

| Metric | Count |
|--------|-------|
| **Critical** | 3 |
| **High** | 7 |
| **Medium** | 10 |
| **Low** | 8 |
| **Total** | 28 |
| **Total files reviewed** | 48 (all layers) |

The two most impactful findings are **C1** (WorkflowWorkerAgent has no context — every workflow step crashes at runtime) and **C2** (EventBus subscriber leak on restart). C1 is a showstopper for any Workflow Runtime usage. C2 causes silent degradation on repeated kernel restarts.

The architecture has a fundamental duality concern — two independent stacks (Node.js and Python) implementing the same features with different session stores, different response schemas, different streaming protocols, and zero cross-synchronization. This should be a deliberate architectural decision with a clear migration path, not an emergent property.
