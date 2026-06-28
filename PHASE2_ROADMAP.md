# ORION Phase 2 — Roadmap & Blocking Issues

**Generated:** 2026-06-28  
**Base:** `v1.0` (tagged)

---

## Part 1: Issues Blocking Future Feature Development

Only issues that would prevent, block, or significantly impair adding new capabilities (Voice, Vision, Browser Automation, Desktop Automation, Long-term Memory, Multi-LLM Routing, Autonomous Task Execution, Plugin Marketplace, Mobile Companion, External API Integrations).

Cosmetic, stylistic, and optional optimization issues are excluded. Architecture is frozen unless a correctness change is required.

### P0 — Must Fix Before Any Phase 2 Feature

| # | Issue | Impact | File(s) | Fix |
|---|-------|--------|---------|-----|
| B1 | **AgentScheduler lifecycle hooks never called** — `start()`/`shutdown()` exist on `AgentScheduler` but it is NOT registered as an `OrionModuleRegistry` module. The background tick loop is never started and never shut down. | **BLOCKS** Autonomous Task Execution — scheduling does not function. Agent-based trigger systems cannot operate. | `app/agents/scheduler.py:19,24`, `app/kernel/boot.py:231-232` | Register as module: `kernel.module_registry.register_module("agent_scheduler", ...)` in boot.py Step 11 |
| B2 | **EventBus.shutdown() not called in FastAPI lifespan** — `EventBus.shutdown()` awaits pending background tasks, but the FastAPI lifespan shutdown handler only calls `kernel.shutdown()`. Background events published via `publish_background()` leak on every restart. | **BLOCKS** Any feature using background events (Autonomous Task Execution, long-running Workflows). Background tasks accumulate across restarts without cleanup. | `services/orion-api/app/main.py:70` | Add `event_bus.shutdown()` call before or after `kernel.shutdown()` in the lifespan handler |
| B3 | **RuntimeSchedulerBridge.submit_and_wait() has no timeout** — If a workflow hangs (infinite loop, blocked tool), the HTTP request hangs indefinitely. There is no configurable timeout. | **BLOCKS** Autonomous Task Execution — any autonomous workflow risks hanging the entire request thread. | `app/workflow_runtime/scheduler_bridge.py:29-41` | Add `asyncio.wait_for(workflow_task, timeout=timeout)` with a configurable timeout parameter |
| B4 | **No database backend for persistence** — Memory engine uses only `JSONStore` (file) or `InMemoryStore` (volatile). No PostgreSQL, SQLite, or Redis. JSONStore saves the entire file on every mutation. | **BLOCKS** Long-term Memory, Mobile Companion, any multi-user scenario. JSON file cannot scale beyond single-user desktop. Frequent full-file writes degrade performance. | `app/memory/store.py:88-105` | Add `SQLAlchemyStore` or `AsyncPGStore` implementing `MemoryStore` interface; wire in `dependencies.py` or `engine.py` |

### P1 — Must Fix for Specific Phase 2 Modules

| # | Issue | Blocks | File(s) | Fix |
|---|-------|--------|---------|-----|
| B5 | **Workflow runtime cancel not exposed via REST API** — `WorkflowRuntimeManager.cancel()` exists but has no HTTP endpoint. The legacy `WorkflowEngine` cancel endpoint (`POST /workflows/{id}/cancel`) targets the old engine, not the new runtime. | **BLOCKS** Autonomous Task Execution management — no way to cancel a running workflow through the API. | `app/workflow_runtime/scheduler_bridge.py:75-76`, `app/api/workflows.py` | Add endpoint `POST /workflows/runtime/{id}/cancel` calling `RuntimeSchedulerBridge.cancel()` |
| B6 | **In-flight tool execution not abortable on workflow cancel** — `WorkflowRuntimeManager.cancel()` cancels the asyncio task but does not propagate to running `tool.execute()`. A running subprocess (e.g. `rm -rf /tmp/data`) completes even after cancel. | **BLOCKS** Autonomous Task Execution + Desktop Automation — cancel is unreliable for destructive operations. Resource waste on cancelled commands. | `app/workflow_runtime/manager.py:197-215`, `app/agents/base.py:179-187` | Add cancellation token propagation through `SharedContext.execute_tool()`; check `asyncio.current_task().cancelled()` at await points in worker agent |
| B7 | **DesktopAutomationService.initialize() called twice** — Called explicitly at `boot.py:123` AND through `LifecycleManager.initialize_all()`. Creates two background `_queue_worker` tasks; the first is leaked (no reference to cancel). | **BLOCKS** Desktop Automation — duplicate background workers cause redundant processing. First worker leaks on shutdown. | `app/kernel/boot.py:122-123`, `app/desktop/automation.py:42-43` | Remove the explicit `await desktop_automation.initialize()` call in boot.py; let the lifecycle manager handle it |
| B8 | **OpenAIEmbeddingProvider is a stub** — Returns `[0.1] * 1536` mock vector regardless of input. | **BLOCKS** Multi-LLM Routing using OpenAI embeddings. Any Phase 2 feature requiring real OpenAI embeddings. | `app/orion/knowledge_embeddings.py:24-31` | Implement real `OpenAIEmbeddingProvider` using `openai` client (unused by default; only affects users who select it) |
| B9 | **PDF parsing is limited to binary text extraction** — No proper PDF library. Fails on scanned documents, no layout preservation. | **BLOCKS** Vision + Document Processing features. Cannot extract structured content from PDFs. | `app/orion/knowledge_document.py:37-44` | Integrate `pypdf` or `pdfplumber` for proper PDF text extraction |

### P2 — Should Fix for Reliability

| # | Issue | Impact | File(s) |
|---|-------|--------|---------|
| B10 | **OrionScheduler has start()/stop() but no initialize()** — LifecycleManager finds `stop()` via fallback (getattr chain) but `start()` with no prior `initialize()` means modules may not be properly initialized before starting. | Reliability concern for scheduler-based features | `app/scheduler/scheduler.py:17,46` |
| B11 | **MissionManager has no lifecycle hooks** — Registered as a module but `initialize()`, `start()`, `shutdown()` are missing. EventBus subscriptions are never set up or cleaned up. | Missions may miss events or leak subscriptions | `app/missions/mission_manager.py` |
| B12 | **LLMRouter has no lifecycle hooks** — Registered as a module but `initialize()`, `start()`, `shutdown()` are missing. | New providers cannot be hot-reloaded; cleanup on shutdown is manual | `app/llm/router.py` |
| B13 | **get_orchestrator() creates lightweight objects per request** — New `IntentClassifier`, `PromptManager`, `EmbeddingsManager` on every API call. | Minor overhead; not blocking but wasteful under load | `app/api/routes.py:23-25` |

### Not Considered Blocking

| Issue | Reason |
|-------|--------|
| `ConversationMemory` dead code | Unused; `MemoryEngine` is the active path. No impact on new features. |
| `app/workflow/engine.py` dead code | Legacy; new features use `workflow_runtime`. No impact. |
| `app/services/ai_service.py`, `app/services/memory_service.py` dead code | Never imported; no impact. |
| `JSONStore.save()` entire file write performance | Would need replacement anyway (B4). Acceptable until database backend exists. |
| `DesktopController` vestigial hooks | No-op methods; no impact. |
| `VectorDB` ChromaDB import optional | JSONVectorStore fallback works fine. Phase 2 can add better backends. |
| Priority inversion in `OrionScheduler` module deps | Doesn't affect correctness; scheduler operates independently. |

---

## Part 2: Phase 2 Module Roadmap

Modules are ranked by **capability impact** (value to users), **architecture impact** (how much they change the core), and **dependency on blocking fixes** (P0/P1 above). Implementation order is designed to minimize rework: fix core issues first, then build from the closest extension points outward.

### Priority Queue

```
Release v1.0 ─► Fix P0/P1 blockers ─► Extend tools & agents ─► New modalities ─► Ecosystem
                      │                       │                      │               │
                      ▼                       ▼                      ▼               ▼
                 [Phase 2.0]           [Phase 2.1]            [Phase 2.2]      [Phase 2.3]
              Infrastructure         Capability Layer       Modality Layer    Ecosystem Layer
```

### Phase 2.0 — Infrastructure Hardening (Month 1)

*Prerequisites: B1, B2, B3, B4 must be resolved.*

| Priority | Module | Effort | Architecture Impact | Rationale |
|----------|--------|--------|-------------------|-----------|
| 1 | **Database Backend** | 2–3 weeks | **HIGH** — New `SQLAlchemyStore` or `AsyncPGStore` implementing `MemoryStore`. Changes `app/core/dependencies.py` and `app/memory/store.py`. Enables Long-term Memory, multi-user sessions. | Foundation for all persistence-dependent features. Must be done first. |
| 2 | **AgentScheduler lifecycle fix** | 1 day | **LOW** — Single registration line in `boot.py:231`. No new classes. | Enables Autonomous Task Execution scheduling. Tiny effort, huge unlock. |
| 3 | **EventBus.shutdown wiring** | 1 hour | **LOW** — Add `event_bus.shutdown()` call in `main.py` lifespan handler. | Correctness fix for all background features. |
| 4 | **Workflow timeout + cancel API** | 2 days | **MEDIUM** — Add timeout to `submit_and_wait()`. Add REST endpoint `POST /workflows/runtime/{id}/cancel`. Changes `scheduler_bridge.py`, `api/workflows.py`. | Required for Autonomous Task Execution management. |

**Architecture changes:** New `MemoryStore` implementation class. New API endpoint. Minor wiring changes. No subsystem restructuring.

### Phase 2.1 — Capability Layer (Month 2)

| Priority | Module | Effort | Architecture Impact | Rationale |
|----------|--------|--------|-------------------|-----------|
| 5 | **Autonomous Task Execution** | 3–4 weeks | **HIGH** — New `AutonomousAgent` extending `BaseAgent`. New scheduler integration. New workflow step types (`loop`, `sub_workflow`, `wait_for_event`). Changes `agents/`, `workflow_runtime/`. | Core Phase 2 differentiator. Uses AgentScheduler + WorkflowRuntime from Phase 2.0. |
| 6 | **Multi-LLM Routing** | 1–2 weeks | **LOW** — Add providers (OpenAI, Anthropic, local models). Update `LLMRouter` with fallback logic, cost tracking. Changes `llm/`. | High value extension. Existing `LLMRouter` supports this. |

**Architecture changes:** New agent class, new step types in `RuntimeStep` enum + handlers in `WorkerAgent`. New LLM provider adapters. Extension of existing interfaces, no restructuring.

### Phase 2.2 — Modality Layer (Months 3–4)

| Priority | Module | Effort | Architecture Impact | Rationale |
|----------|--------|--------|-------------------|-----------|
| 7 | **Browser Automation** | 2–3 weeks | **MEDIUM** — New `BrowserAutomationTool` using Playwright/Selenium. Real (not stubbed) browser control. Updates `DesktopAutomationService` or new service. | High user value. Existing `desktop_automation` provides partial headless browser — needs production hardening. |
| 8 | **Desktop Automation** | 2–3 weeks | **MEDIUM** — Production DesktopController with GUI automation (PyAutoGUI, key simulations). Replaces vestigial `DesktopController` hooks. | Addresses B7 (double init). Completes the desktop automation vision. |
| 9 | **Vision** | 3–4 weeks | **MEDIUM** — Image input support in Gemini/LLM providers. Screen capture tool. Document OCR via `pytesseract` or Gemini Vision API. Updates `knowledge_document.py` for scanned PDFs (B9). | Multimodal capability. Leverages existing LLM provider streaming infrastructure. |
| 10 | **Voice Assistant** | 3–4 weeks | **MEDIUM** — New audio input/output via WebRTC or WebSocket. Speech-to-text (Whisper) and text-to-speech integration. New API endpoints for audio streaming. | Adds speech modality. New I/O paths but reuses core pipeline (Orchestrator → Planner → Tools → LLM). |

**Architecture changes:** New tools (BrowserAutomationTool). New API endpoints for voice. Modifications to `KnowledgeDocument` for OCR. Existing `BaseTool`/`BaseAgent` interfaces accommodate all additions.

### Phase 2.3 — Ecosystem Layer (Months 5–6)

| Priority | Module | Effort | Architecture Impact | Rationale |
|----------|--------|--------|-------------------|-----------|
| 11 | **External API Integrations** | 2–3 weeks | **LOW** — New tool implementations for popular APIs (Slack, GitHub, Jira, Gmail, etc.). Each is a `BaseTool` subclass. | High value. Zero architecture change — pure additive tool development. |
| 12 | **Plugin Marketplace** | 4–6 weeks | **HIGH** — Plugin manifest format, sandboxed plugin execution, registry/discovery endpoint, plugin installation flow (CLI + API). Changes to multiple subsystems for sandboxing. | Enables third-party ecosystem. Highest architecture impact — requires new security/sandboxing infrastructure, plugin ABI, versioning. |
| 13 | **Mobile Companion** | 4–6 weeks | **MEDIUM** — React Native app. New mobile-specific API endpoints (push notifications, file upload, offline queue). Server-side: session sync, notification service. | New client. Server changes are additive (new endpoints). Session syncing needs the database backend (Phase 2.0). |

**Architecture changes:** Plugin sandbox architecture (new subsystem). Mobile API layer. Tool ecosystem (additive only).

---

## Dependency Graph

```
Phase 2.0                          Phase 2.1                      Phase 2.2                    Phase 2.3
──────────                        ──────────                      ──────────                   ──────────
                                                                                                
Database ──────────────► Long-term Memory ─────────────► Vision (OCR storage)                   
Backend                        │                              │                                 
(B4)                           │                              │                                 
                               │                              ▼                                 
AgentScheduler ───────► Autonomous Task ─────────────► Browser Automation                      
Fix (B1)                     Execution                     Desktop Automation                    
                               │                              │                                 
EventBus ─────────────────────►│                              │                                 
Shutdown (B2)                  │                              │                                 
                               │                              ▼                                 
Workflow Timeout ─────────────►│                       Voice Assistant                          
+ Cancel API (B3, B5)          │                              │                                 
                               │                              │                                 
Multi-LLM Routing ◄────────────┤                              │                                 
(B8)                           │                              │                                 
                               │                              ▼                                 
                         Plugin Marketplace ◄────── External API Integrations                  
                               │                              │                                 
                               ▼                              ▼                                 
                         Mobile Companion                                                       
```

---

## Effort Summary

| Phase | Duration | Features | Architecture Impact |
|-------|----------|----------|-------------------|
| 2.0 — Infrastructure | ~1 month | 4 issues (B1–B4 fixes) | LOW — Wiring changes, new store class |
| 2.1 — Capability | ~1 month | 2 features (Autonomous Execution, Multi-LLM) | MEDIUM — New agent, step types, providers |
| 2.2 — Modality | ~2 months | 4 features (Browser, Desktop, Vision, Voice) | MEDIUM — New tools, new I/O paths |
| 2.3 — Ecosystem | ~2 months | 3 features (APIs, Marketplace, Mobile) | HIGH — Plugin sandbox, new client |

**Total:** ~6 months for full Phase 2.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Plugin sandbox security | Medium | Critical | Start sandbox design early; use containerization or WASM isolation |
| Voice latency | Medium | High | Implement streaming audio; use WebSocket for real-time |
| Vision token costs | High | Medium | Implement image compression; use cache; user-configurable quality |
| Browser automation fragility | High | Medium | Headless browser selectors break; use AI-powered element selection |
| Database migration | Low | High | Keep JSONStore as fallback; gradual migration with feature flag |
