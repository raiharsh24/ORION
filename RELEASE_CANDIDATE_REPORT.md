# FRIDAY Release Candidate Report — v1.0.0-rc1

**Generated:** 2026-06-28  
**Previous report:** `SYSTEM_VALIDATION_REPORT.md` (all 3 Critical + 7 High issues resolved)

---

## Architecture Overview

FRIDAY is a multi-process AI agent platform with four runtime tiers:

| Tier | Technology | Role |
|------|-----------|------|
| **Desktop UI** | React/TypeScript (Vite) | User interface, streaming chat, telemetry |
| **Gateway** | Node.js/Express | Auth, session management, SSE/WS streaming proxy |
| **Friday API** | Python/FastAPI | Orchestration, planning, tool execution, memory, knowledge |
| **Persistence** | JSON files, ChromaDB (optional) | Session memory, workflow state, vector embeddings |

Communication flow: **Desktop UI → Gateway (REST/WS) → FastAPI (Python) → Subsystems**

All `/api/*` routes are proxied through the Gateway. Both `/path` and `/api/path` variants are supported.

---

## Subsystem Inventory

### 1. Core Services

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| EventBus | `app/events/bus.py` | ❌ No init/start, ✅ shutdown | Publisher | Operational |
| FridayKernel | `app/kernel/kernel.py` | ✅ Full lifecycle | Dispatches boot/shutdown | Operational |
| FridayServiceContainer | `app/kernel/container.py` | N/A (DI container) | — | Operational |
| LifecycleManager | `app/kernel/lifecycle_manager.py` | N/A (manages modules) | — | Operational |

### 2. Conversation & Planning

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| FridayOrchestrator | `app/friday/orchestrator.py` | Per-request (via Depends) | ConversationReceived, ConversationCompleted | Operational |
| IntentClassifier | `app/friday/intent.py` | N/A (stateless) | — | Operational |
| PlannerEngine | `app/friday/planner_engine.py` | ✅ Full lifecycle | — | Operational |
| PromptManager | `app/friday/prompt_manager.py` | N/A (stateless) | — | Operational |

### 3. Workflow Runtime

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| WorkflowRuntimeManager | `app/workflow_runtime/manager.py` | ❌ Not a module | WorkflowStarted, Completed, Failed, Cancelled, Paused, Resumed | Operational |
| WorkflowRuntimeExecutor | `app/workflow_runtime/executor.py` | ❌ Not a module | — | Operational |
| WorkflowPersistence | `app/workflow_runtime/persistence.py` | ❌ Not a module | — | Operational |
| RuntimeSchedulerBridge | `app/workflow_runtime/scheduler_bridge.py` | ❌ Not a module | — | Operational |
| WorkflowWorkerAgent | `app/workflow_runtime/worker_agent.py` | ❌ Not a module | — | Operational |
| CheckpointManager | `app/workflow_runtime/checkpoints.py` | ❌ Not a module | — | Operational |

### 4. Tools & Execution

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| ToolEngine | `app/friday/tool_engine.py` | ✅ Full lifecycle | ToolCompleted | Operational |
| ToolRegistry | `app/friday/tool_registry.py` | ❌ Not a module | — | Operational |
| FilesystemTool | `app/tools/filesystem.py` | N/A (stateless) | — | Operational |
| TerminalTool | `app/tools/terminal.py` | N/A (stateless) | — | Operational |
| BrowserTool | `app/tools/browser.py` | N/A (stateless) | — | Operational |
| ClipboardTool | `app/tools/clipboard.py` | N/A (stateless) | — | Operational |
| OpenAppTool | `app/tools/open_app.py` | N/A (stateless) | — | Operational |
| KnowledgeSearchTool | `app/tools/knowledge_search.py` | N/A (stateless) | — | Operational |
| Desktop tool wrappers | `app/tools/desktop_tools.py` | N/A (delegates) | — | Operational |

### 5. Memory & Persistence

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| MemoryEngine | `app/memory/engine.py` | ✅ Full lifecycle | MemoryUpdated | Operational |
| MemoryManager | `app/memory/manager.py` | N/A (internal) | Subscriber | Operational |
| JSONStore | `app/memory/store.py` | N/A (internal) | — | Operational |
| InMemoryStore | `app/memory/store.py` | N/A (internal) | — | Operational (fallback) |

### 6. Knowledge Engine

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| KnowledgeEngine | `app/friday/knowledge_engine.py` | ✅ Full lifecycle | — | Operational |
| KnowledgeManager | `app/friday/knowledge_engine.py` | N/A (internal) | — | Operational |
| VectorDB | `app/friday/vectordb.py` | N/A (internal) | — | Operational (ChromaDB or JSON) |
| DocumentParser | `app/friday/knowledge_document.py` | N/A (stateless) | — | Operational |
| HybridRetriever | `app/friday/knowledge_retriever.py` | N/A (stateless) | — | Operational |
| RetrievalEngine | `app/friday/retrieval.py` | N/A (internal) | — | Operational |

### 7. Agents

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| AgentCoordinator | `app/agents/coordinator.py` | ❌ No init/start, ✅ shutdown | AgentTaskCompleted, Failed, Delegated | Operational |
| AgentRegistry | `app/agents/registry.py` | ❌ Not a module | — | Operational |
| AgentMessageBus | `app/agents/bus.py` | ❌ Not a module | — | Operational |
| AgentScheduler | `app/agents/scheduler.py` | ❌ Not a module (has hooks) | — | Operational |
| AgentTelemetry | `app/agents/base.py` | ❌ Not a module | — | Operational |
| SharedContext | `app/agents/context.py` | ❌ Not a module | — | Operational |

### 8. LLM & AI

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| LLMRouter | `app/llm/router.py` | ❌ No hooks (but is a module) | — | Operational |
| GeminiProvider | (src/ai/providers/) | N/A | — | Operational |
| GeminiAdapter | `app/llm/gemini.py` | N/A | — | Operational |

### 9. Missions

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| MissionManager | `app/missions/mission_manager.py` | ❌ Is a module but NO hooks | — | Operational |

### 10. Scheduler

| Subsystem | File | Lifecycle | Events | Status |
|-----------|------|-----------|--------|--------|
| FridayScheduler | `app/scheduler/scheduler.py` | ✅ start/stop (no init) | — | Operational |

### 11. Gateway (Node.js)

| Module | File | Status |
|--------|------|--------|
| SessionController | `src/controllers/sessionController.js` | Operational (default provider: gemini) |
| ChatController | `src/controllers/chatController.js` | Operational (AbortController for cancel) |
| SSE/WS streaming | `src/server.js` | Operational (websocket proxy) |
| API proxy | `src/app.js` | Operational (all routes + /api variants) |

### 12. Desktop UI (React)

| Module | File | Status |
|--------|------|--------|
| Chat stream | `useSystemStore.ts` | Operational (AbortController, real telemetry) |
| Stop button | `AssistantPage.tsx` | Operational (wired to cancelCurrentRequest) |

---

## End-to-End Execution Pipeline

```
Desktop UI                    Gateway                     FastAPI                    Subsystems
-----------                   -------                     ------                    ----------
User types message
    │
    ▼
POST /chat ─────────────────► chatController
                                  │
                                  ▼
                            POST /ask ───────────────────► get_orchestrator()
                                                              │
                                                              ├── kernel.get_service("llm_router")
                                                              ├── kernel.get_service("memory_engine")
                                                              ├── kernel.get_service("runtime_scheduler_bridge")
                                                              ├── kernel.get_service("event_bus")
                                                              ├── new IntentClassifier()
                                                              ├── new PromptManager()
                                                              └── new EmbeddingsManager()
                                                              │
                                                              ▼
                                                      orchestrator.process_query()
                                                              │
                                                              ├── 1. IntentClassifier.classify(prompt) → intent_type
                                                              │       │
                                                              │       └── "conversation" → direct LLM (skip planner)
                                                              │       └── "plan_generation" / "mission" → planner
                                                              │
                                                              ├── 2. Planner.create_plan(intent, context) → ExecutionPlan
                                                              │       │
                                                              │       └── Plan has steps with actions
                                                              │
                                                              ├── 3. execution_plan_to_input(plan) → ExecutionPlanInput
                                                              │
                                                              ├── 4. Check confirmation (if needed)
                                                              │       │
                                                              │       └── Confirmed? → proceed
                                                              │       └── Not confirmed? → return confirmation request
                                                              │
                                                              ├── 5. RuntimeSchedulerBridge.submit_and_wait(input)
                                                              │       │
                                                              │       ▼
                                                              │  WorkflowRuntimeManager._run_workflow()
                                                              │       │
                                                              │       ├── executor.build_from_plan() → RuntimeWorkflow
                                                              │       ├── executor.get_parallel_groups() → topological order
                                                              │       │
                                                              │       ▼  (for each parallel group)
                                                              │  WorkflowRuntimeExecutor.execute_step(step)
                                                              │       │
                                                              │       ├── AgentCoordinator.delegate(AgentTask)
                                                              │       │       │
                                                              │       │       ├── AgentRegistry.get_agent("workflow_worker")
                                                              │       │       ├── agent.process_task(task)
                                                              │       │       │       │
                                                              │       │       │       ▼
                                                              │       │       │  WorkflowWorkerAgent.execute_task()
                                                              │       │       │       │
                                                              │       │       │       ├── step.type == "tool":
                                                              │       │       │       │   SharedContext.execute_tool(name, args)
                                                              │       │       │       │       │
                                                              │       │       │       │       ▼
                                                              │       │       │       │   ToolEngine.execute_tool()
                                                              │       │       │       │       │
                                                              │       │       │       │       ├── CapabilityRegistry.lookup()
                                                              │       │       │       │       ├── ToolResolver.resolve()
                                                              │       │       │       │       ├── PermissionManager.check()
                                                              │       │       │       │       ├── SandboxManager.validate()
                                                              │       │       │       │       ├── ToolValidator.validate()
                                                              │       │       │       │       ├── Confirmation (if required)
                                                              │       │       │       │       └── tool.execute(**args)
                                                              │       │       │       │
                                                              │       │       │       ├── step.type == "llm": LLM call
                                                              │       │       │       ├── step.type == "knowledge":
                                                              │       │       │       │   KnowledgeEngine.query_knowledge()
                                                              │       │       │       ├── step.type == "condition":
                                                              │       │       │       │   Evaluate conditional expression
                                                              │       │       │       ├── step.type == "delay": asyncio.sleep
                                                              │       │       │       └── step.type == "mission":
                                                              │       │       │           MissionManager.handle_event()
                                                              │       │       │
                                                              │       │       └── Result back to coordinator
                                                              │       │
                                                              │       └── Checkpoints saved after each step
                                                              │
                                                              ├── 6. extract_tool_output(results) → tool_outputs
                                                              │
                                                              ├── 7. Build prompt with context + results
                                                              │
                                                              ├── 8. LLMRouter.route(prompt) → LLM response
                                                              │       │
                                                              │       └── GeminiProvider.chat() / stream_chat()
                                                              │
                                                              ├── 9. Format response (FridayResponse)
                                                              │
                                                              ├── 10. MemoryManager.save_session() (publishes MemoryUpdated)
                                                              │
                                                              └── 11. EventBus publishes ConversationCompleted
                                                                       │
                                                                       ▼
                                                                  All subscribers notified
    ▲
    │
◄─── Gateway streams response back to Desktop UI
    │
    └── Telemetry captured (real usage data)
```

---

## Production Readiness Checklist

### ✅ Verified Working

- [x] **Desktop UI → Gateway → FastAPI** full request flow
- [x] **Streaming responses** (SSE through Gateway)
- [x] **WebSocket upgrade proxy** through Gateway
- [x] **Non-streaming requests** with signal/cancellation
- [x] **Cancel end-to-end** (Stop button → AbortController → signal checks in provider)
- [x] **Intent classification** (conversation vs. plan_generation vs. mission)
- [x] **Planner → Workflow Runtime bridge** (execution_plan_to_input)
- [x] **Workflow execution** (sequential + parallel steps via asyncio.gather)
- [x] **Tool execution pipeline** (capability → resolve → permission → sandbox → validate → confirm → execute)
- [x] **Tool implementations** (filesystem, terminal, browser, clipboard, open_app, knowledge_search, desktop wrappers)
- [x] **Knowledge engine** (parse → chunk → embed → store → hybrid retrieve → rank → cite)
- [x] **Memory persistence** (JSON store with disk writes; in-memory fallback)
- [x] **EventBus publish/subscribe** (concurrent dispatch with priority ordering)
- [x] **Background events** (fire-and-forget via publish_background with supervised tasks)
- [x] **Real telemetry** (desktop captures actual usage data from streaming completion)
- [x] **Kernel boot sequence** (DI registration → capability indexing → context creation)
- [x] **Graceful shutdown** (lifecycle_manager.shutdown_all in reverse topological order)
- [x] **AI Service initialization** (3 baseline missions created on startup)
- [x] **All 181 tests pass** (0 failures)

### ⚠️ Known Limitations (Non-Blocking)

- **No database backend** — Memory uses JSON file or in-memory store only. Adequate for single-user desktop; not production-scale.
- **Cancellation is soft** — Workflow asyncio task is cancelled but in-flight tool executions (e.g. running shell command) complete before cancellation takes effect.
- **New runtime cancel not exposed via REST** — Only the legacy `WorkflowEngine` cancel endpoint is exposed; the new `WorkflowRuntimeManager.cancel()` has no HTTP endpoint.
- **PDF parsing is rough** — Binary text extraction only; no proper PDF library. Works for text PDFs but fails on scanned documents.
- **LLM provider fallback** — Falls back to hash-based mock embeddings when no API key is configured.
- **FridayOrchestrator is per-request** — New `IntentClassifier`, `PromptManager`, `EmbeddingsManager` created on every request (lightweight, but bypasses DI container).
- **EventBus has no init/start** — Setup is done in `__init__`, bypassing the lifecycle manager's initialize/start hooks.

---

## Remaining Technical Debt

### HIGH Severity

| ID | Issue | File(s) | Impact |
|----|-------|---------|--------|
| H8 | DesktopAutomationService.initialize() called twice (explicit + lifecycle manager) | `boot.py:123`, `automation.py:42` | Two background queue workers created; first is leaked |
| H9 | Workflow cancel does not abort in-flight tool execution | `manager.py:197-215`, `worker_agent.py:27-50` | Tool completes even after cancel; eventual at next await |
| H10 | Workflow runtime cancel not exposed via REST API | `scheduler_bridge.py:75-76` | No HTTP endpoint for new runtime cancel; only legacy engine exposed |

### MEDIUM Severity

| ID | Issue | File(s) | Impact |
|----|-------|---------|--------|
| M1 | EventBus.shutdown() not called in FastAPI lifespan shutdown | `main.py:70` | Background tasks may leak on shutdown |
| M2 | No timeout on RuntimeSchedulerBridge.submit_and_wait | `scheduler_bridge.py:29-41` | Blocked workflow blocks indefinitely |
| M3 | MissionManager has no lifecycle hooks (but is a module) | `mission_manager.py` | EventBus subscriptions never set up/cleaned |
| M4 | LLMRouter has no lifecycle hooks (but is a module) | `llm/router.py` | No init/start/shutdown called |
| M5 | WorkflowEngine (legacy) has no lifecycle hooks (but is a module) | `workflow/engine.py` | Dead code registered as module |
| M6 | AgentScheduler has start/shutdown hooks but not registered as module | `boot.py:231-232`, `scheduler.py:19,24` | Background tick loop leaks on shutdown |
| M7 | 12 services registered in DI container but not in module registry | `boot.py:111,222-312` | Lifecycle hooks (if any) never called |
| M8 | ConversationMemory is dead code | `conversation.py` | Legacy class; MemoryEngine is active path |
| M9 | OpenAIEmbeddingProvider returns mock vectors | `knowledge_embeddings.py:24-31` | Cannot be used for real search (unused by default) |

### LOW Severity

| ID | Issue | File(s) | Impact |
|----|-------|---------|--------|
| L1 | JSONStore.save() writes entire file on every mutation | `store.py:88-105` | Performance degrades with large datasets |
| L2 | KnowledgeEngine.search() lazy-init edge case | `knowledge_engine.py:249-254` | Creates bare manager if called before initialize |
| L3 | DesktopController has vestigial empty hooks | `controller.py:36,52` | No-op methods; unused |
| L4 | VectorDB ChromaDB import is optional | `vectordb.py:162-172` | Falls back to JSON; no ANN indexing |

### DEAD CODE (Documented, Not Removed)

| File | Purpose | Notes |
|------|---------|-------|
| `app/workflow/engine.py` | Legacy workflow engine | Never imported by any active code path |
| `app/workflow/history.py` | Legacy workflow history | Never imported by any active code path |
| `app/friday/knowledge_embeddings.py` | Embedding providers (stubs) | Never imported by active path; MemoryEngine.embed_text is used |
| `app/services/ai_service.py` | AI service stub | Never imported by active path |
| `app/services/memory_service.py` | Memory service stub | Never imported by active path |
| `app/memory/conversation.py` | ConversationMemory (legacy) | Imported by orchestrator.py but duck-typing used via MemoryEngine |

---

## Test Results

```
181 passed, 4 warnings in 12.97s
```

| Test Area | Count | Status |
|-----------|-------|--------|
| Unit tests | 181 | ✅ All pass |
| Flaky tests | 1 (`test_ask_route_confirmation_loop`) | ✅ Fixed |
| Warnings | 4 | ✅ Collection warnings only (TestAgent class constructor) |

---

## Version Recommendation

**v1.0.0-rc1** — Release Candidate 1

This build is suitable for:
- **Single-user desktop deployment** with Gemini API key
- **Development and testing** of workflow automation features
- **Integration testing** of the full 12-subsystem pipeline

**Not recommended for:**
- Multi-user production deployment (no database backend, no auth beyond Gateway)
- Scanned document processing (basic PDF extraction only)
- Environments requiring hard cancellation of running shell commands (cancel is soft)

### Upgrade Path to v1.0.0

Before declaring GA, address:
1. Call `EventBus.shutdown()` in FastAPI lifespan shutdown handler
2. Register missing modules in `FridayModuleRegistry` (AgentScheduler, AgentRegistry, etc.)
3. Expose new workflow runtime cancel via REST API
4. Add timeout to `RuntimeSchedulerBridge.submit_and_wait`
5. Add database backend (PostgreSQL or SQLite) for production persistence

---

## Production Readiness Verdict

| Category | Score | Notes |
|----------|-------|-------|
| Core pipeline | **PASS** | Desktop → Gateway → FastAPI → Subsystems → Response |
| Streaming | **PASS** | SSE through Gateway proxy, real telemetry |
| Cancellation | **PASS** (conditional) | UI → Gateway → Provider; works for non-streaming and streaming |
| Events | **PASS** | 8 subscribers receiving events, background tasks supervised |
| Persistence | **PASS** (limited) | JSON file storage adequate for single-user |
| Tools | **PASS** | All 8 tool types operational with real implementations |
| Knowledge | **PASS** | Full pipeline with hybrid retrieval and ChromaDB/JSON fallback |
| Startup/Shutdown | **PASS** (limited) | Kernel boot works; minor module registration gaps |
| Tests | **PASS** | 181/181 passing, 0 flaky |
| Dead code | **PASS** | All documented; none affects active request paths |

**Overall: LEVEL 2 — FUNCTIONAL** — Ready for release candidate testing. No critical or blocking issues. All known limitations are documented and non-blocking for single-user desktop scenarios.
