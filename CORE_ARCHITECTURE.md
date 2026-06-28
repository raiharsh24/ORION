# FRIDAY Core v1.0 Architecture

**Tag:** `v1.0`  
**Generated:** 2026-06-28

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Process Architecture](#process-architecture)
3. [Subsystem Responsibilities](#subsystem-responsibilities)
4. [Execution Flow](#execution-flow)
5. [Dependency Graph](#dependency-graph)
6. [Extension Points](#extension-points)
7. [Public Interfaces](#public-interfaces)
8. [Project Layout](#project-layout)

---

## System Overview

FRIDAY is a three-tier AI agent platform:

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────────────────┐
│   Desktop UI    │ ◄──► │    Gateway      │ ◄──► │        Friday API             │
│  (React/TS)     │     │  (Node.js)      │     │      (Python/FastAPI)         │
│                 │     │                 │     │                              │
│  Streaming chat │     │  Auth/Sessions  │     │  Orchestrator ─► Planner     │
│  Real telemetry │     │  SSE/WS proxy   │     │       │                      │
│  Stop button    │     │  REST proxy     │     │       ├► Workflow Runtime    │
│                 │     │                 │     │       ├► Tool Engine         │
│                 │     │                 │     │       ├► Memory Engine       │
│                 │     │                 │     │       ├► Knowledge Engine    │
│                 │     │                 │     │       ├► Agent Coordinator   │
│                 │     │                 │     │       └► LLM Router          │
└─────────────────┘     └─────────────────┘     └──────────────────────────────┘
```

All production code lives in `services/friday-api/app/` (Python backend), `services/gateway/src/` (Node.js middleware), and `apps/desktop/src/` (React frontend).

---

## Process Architecture

### Boot Sequence

```
FridayKernel.boot()
    │
    ├── BootManager.run_boot_sequence(config)
    │       │
    │       ├── Step 3: EventBus (pub/sub)
    │       ├── Step 4: MemoryEngine (persistence)
    │       ├── Step 5: KnowledgeEngine (vector search)
    │       ├── Step 6: Planner (plan generation)
    │       ├── Step 7: DesktopController, ToolRegistry, ToolEngine
    │       ├── Step 8: MissionManager (missions)
    │       ├── Step 9: WorkflowEngine (legacy)
    │       ├── Step 10: Scheduler, LLMRouter
    │       ├── Step 11: Multi-Agent Runtime (AgentCoordinator, etc.)
    │       └── Step 12: Workflow Runtime (WorkflowRuntimeManager, etc.)
    │
    ├── LifecycleManager.initialize_all()
    ├── LifecycleManager.start_all()
    └── KernelState.READY
```

### Shutdown Sequence

```
FridayKernel.shutdown()
    │
    ├── Dispatch KernelShutdown event
    ├── LifecycleManager.shutdown_all() (reverse dependency order)
    └── Unregister all services from container
```

### Request Flow

```
Desktop UI              Gateway               FastAPI
    │                      │                     │
    │ POST /chat           │                     │
    ├─────────────────────►│                     │
    │                      │ POST /ask           │
    │                      ├────────────────────►│
    │                      │                     ├── get_orchestrator()
    │                      │                     │   (resolves DI singletons,
    │                      │                     │    creates per-request objects)
    │                      │                     │
    │                      │                     ├── orchestrator.process_query()
    │                      │                     │   │
    │                      │                     │   ├── IntentClassifier.classify()
    │                      │                     │   ├── Planner.create_plan()
    │                      │                     │   ├── RuntimeBridge.submit_and_wait()
    │                      │                     │   ├── LLMRouter.route()
    │                      │                     │   └── MemoryManager.save_session()
    │                      │                     │
    │                      │ ◄────────────────────┤
    │ ◄───────────────────┤                      │
```

---

## Subsystem Responsibilities

### 1. FridayKernel (`app/kernel/kernel.py`)

Central system kernel managing lifecycle, DI container, module registry, capability registry, health monitoring, and event publication. Singleton accessed via `FridayKernel.get_instance()`.

**Key responsibilities:**
- Boot/shutdown orchestration via `BootManager` + `LifecycleManager`
- Service registration and resolution via `FridayServiceContainer`
- Module lifecycle tracking via `FridayModuleRegistry`
- Capability indexing via `FridayCapabilityRegistry`
- Health check aggregation via `FridayHealthMonitor`
- Event dispatch to `EventBus`

### 2. EventBus (`app/events/bus.py`)

Priority-ordered publish/subscribe event system supporting wildcard patterns, middleware interceptors, foreground dispatch with concurrent handler groups, and supervised background tasks.

**Event lifecycle:**
1. Middleware chain (can drop or transform events)
2. Wildcard pattern matching against subscriber registry
3. Group subscribers by priority
4. Execute groups sequentially (lowest priority first)
5. Within each group, execute handlers concurrently via `asyncio.gather(return_exceptions=True)`

**Key events:**
- `ConversationReceived`, `ConversationCompleted` — request lifecycle
- `ToolCompleted` — tool execution result
- `MemoryUpdated` — memory persistence
- `WorkflowStarted`, `WorkflowPaused`, `WorkflowCompleted`, `WorkflowFailed`, `WorkflowCancelled` — workflow lifecycle
- `AgentTaskCompleted`, `AgentTaskFailed`, `AgentTaskDelegated` — agent task lifecycle
- `KernelBooting`, `KernelReady`, `KernelShutdown` — kernel lifecycle

### 3. FridayOrchestrator (`app/friday/orchestrator.py`)

Per-request coordinator that wires intent classification → planning → execution → LLM response → memory persistence.

**Key flow:**
1. Classify intent (conversation vs. plan_generation vs. mission)
2. For plan intents: create plan via `Planner`, convert via `execution_plan_to_input()`, execute via runtime bridge
3. For conversation intents: direct LLM call
4. Build prompt with context + tool outputs
5. Route to LLM via `LLMRouter`
6. Save session to `MemoryEngine`
7. Publish `ConversationCompleted` event

### 4. Planner (`app/friday/planner.py` / `app/friday/planner_engine.py`)

Generates `ExecutionPlan` with typed steps (tool, llm, knowledge, condition, delay, mission, notification, agent_task). The `PlannerEngine` is the lifecycle-managed version with `initialize()`/`start()`/`shutdown()`.

### 5. Workflow Runtime (`app/workflow_runtime/`)

Executes plans as `RuntimeWorkflow` instances with topological step ordering, parallel group execution, checkpoint persistence, pause/resume/cancel, and agent delegation.

**Components:**
- `WorkflowRuntimeManager` — lifecycle of workflow runs (start, pause, resume, cancel, recover)
- `WorkflowRuntimeExecutor` — step execution, plan→workflow conversion, variable resolution
- `WorkflowPersistence` — file-based JSON persistence of workflow state
- `CheckpointManager` — file-based step-level checkpointing
- `RuntimeSchedulerBridge` — orchestration layer bridge (submit_plan → manager)
- `WorkflowWorkerAgent` — handles 8 step types (tool, llm, knowledge, condition, delay, mission, notification, agent_task)

### 6. Tool Engine (`app/friday/tool_engine.py` + `app/tools/`)

Complete tool execution pipeline:
1. Capability lookup (`CapabilityRegistry`)
2. Tool resolution (`ToolResolver`)
3. Permission check (`PermissionManager`)
4. Sandbox validation (`SandboxManager`)
5. Argument validation (`ToolValidator`)
6. User confirmation (if `requires_confirmation()` returns True)
7. Async execution with timeout (`asyncio.wait_for`)

**Registered tools:**
| Tool | File | Type | Description |
|------|------|------|-------------|
| `read_file` | `app/tools/filesystem.py` | Real | Read file contents |
| `write_file` | `app/tools/filesystem.py` | Real | Write content to file |
| `delete_file` | `app/tools/filesystem.py` | Real | Delete file |
| `list_files` | `app/tools/filesystem.py` | Real | List directory contents |
| `execute_command` | `app/tools/terminal.py` | Real | Execute shell command (17 allowed, 20 blocked) |
| `browser_search` | `app/tools/browser.py` | Real | Fetch URL content |
| `clipboard_copy` | `app/tools/clipboard.py` | Real | Copy to clipboard |
| `clipboard_read` | `app/tools/clipboard.py` | Real | Read from clipboard |
| `open_app` | `app/tools/open_app.py` | Real | Launch desktop application |
| `desktop.*` | `app/tools/desktop_tools.py` | Real (wrapper) | Delegates to DesktopController |
| `knowledge_search` | `app/tools/knowledge_search.py` | Real | Semantic KB search |

### 7. Memory Engine (`app/memory/`)

Session/user/project memory with two backends:
- `JSONStore` — persists to JSON file on every mutation
- `InMemoryStore` — volatile dict (fallback)

`MemoryEngine` is lifecycle-managed (`initialize()`→`start()`→`shutdown()`). `MemoryManager` provides CRUD operations for session, user, and project memory layers. Publisher of `MemoryUpdated` event.

### 8. Knowledge Engine (`app/friday/knowledge_engine.py`)

Full knowledge pipeline:
1. `DocumentParser` — parses JSON, PDF, TXT, MD, code
2. `ChunkManager` — Fixed, Sliding Window, or Recursive chunking
3. `EmbeddingsManager` — Google Generative AI or hash-based mock embeddings
4. `VectorDB` — ChromaDB or `JSONVectorStore` fallback
5. `HybridRetriever` — combines cosine similarity with keyword overlap
6. `KnowledgeRanker` — threshold filter + top-K
7. `ContextAssembler` — formats into XML `<KnowledgeSource>` blocks

### 9. Multi-Agent Runtime (`app/agents/`)

Agent delegation system with:
- `AgentCoordinator` — delegates tasks to registered agents, tracks completion
- `AgentRegistry` — register/unregister agent instances
- `AgentMessageBus` — inter-agent messaging over EventBus
- `AgentScheduler` — periodic background tick
- `SharedContext` — shared state accessible by agents, tool execution fallback
- `BaseAgent` — abstract class with `process_task()`, `cancel_task()`, lifecycle hooks

### 10. LLM Router (`app/llm/router.py`)

Provider-agnostic router. Registers providers and routes prompts by name. Default provider is Gemini (`GeminiAdapter`).

### 11. FridayServiceContainer (`app/kernel/container.py`)

DI container supporting three scopes:
- `singleton` — always returns same instance
- `transient` — new instance per `get()` call
- `factory` — parameterized factory callable

### 12. LifecycleManager (`app/kernel/lifecycle_manager.py`)

Manages module lifecycle transitions in topological order:
- `initialize_all()` — forward order
- `start_all()` — forward order
- `shutdown_all()` — reverse order
- `pause_all()` / `resume_all()` — reverse/forward order

Supports hook name fallbacks: `initialize`/`init`, `shutdown`/`stop`/`close`.

### 13. Gateway (Node.js, `services/gateway/`)

Express-based middleware providing:
- Session management (`sessionController.js`)
- Chat proxying to Python API (`chatController.js`)
- SSE streaming proxy (`server.js`)
- WebSocket upgrade handler (`server.js`)
- REST API proxy for all `/api/*` and root-level routes

### 14. Desktop UI (React/TypeScript, `apps/desktop/`)

Single-page application with:
- Streaming chat via `useSystemStore.ts`
- Real telemetry capture (token usage, wall-clock timing)
- Cancel/stop button wired to `AbortController`
- TypeScript interfaces in `src/types/`

---

## Dependency Graph

```
FridayKernel
    ├── BootManager
    │   └── FridayServiceContainer (DI)
    ├── FridayModuleRegistry
    ├── FridayCapabilityRegistry
    ├── FridayLifecycleManager
    └── FridayHealthMonitor

Service Registration Order (boot.py):
    event_bus ──────────────────────┐
        │                           ├──► tool_engine
        ├──► memory_engine ─────────┤
        ├──► knowledge_engine ──────┤
        │                           ├──► mission_engine
        ├──► planner ───────────────┤
        │                           ├──► workflow_engine (legacy)
        ├──► desktop_controller ────┤
        ├──► tool_registry ─────────┤
        ├──► desktop_automation ────┤
        │                           ├──► scheduler
        └──► llm_router ────────────┤
                                    ├──► agent_coordinator
                                    │       ├── agent_message_bus
                                    │       ├── agent_registry
                                    │       ├── agent_scheduler
                                    │       ├── agent_telemetry
                                    │       └── shared_context
                                    │
                                    └──► workflow_runtime_manager
                                            ├── workflow_persistence
                                            ├── checkpoint_manager
                                            ├── workflow_runtime_executor
                                            │   └── agent_coordinator
                                            └── runtime_scheduler_bridge

Runtime Dependencies (request flow):
    FridayOrchestrator
        ├── LLMRouter (kernel.get_service)
        ├── MemoryEngine (kernel.get_service)
        ├── RuntimeSchedulerBridge (kernel.get_service)
        ├── EventBus (kernel.get_service)
        ├── ToolRegistry (from core.dependencies)
        ├── IntentClassifier (new per request)
        ├── PromptManager (new per request)
        └── EmbeddingsManager (new per request)
```

---

## Extension Points

### 1. Tools

Implement `BaseTool` interface and register with `ToolRegistry`:

```python
class BaseTool(ABC):
    name: str
    description: str
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass
    
    def requires_confirmation(self) -> bool:
        return False
```

Registration: `tool_registry.register(MyTool())`

### 2. Agents

Extend `BaseAgent` and register with `AgentRegistry`:

```python
class BaseAgent(ABC):
    agent_id: str
    name: str
    
    @abstractmethod
    async def execute_task(self, task: AgentTask) -> Any:
        pass
    
    async def process_task(self, task: AgentTask) -> Any:
        # Default implementation with timeout
        
    def cancel_task(self, task_id: str) -> None:
        # Set cancellation flag
```

Registration: `agent_registry.register(MyAgent())`

### 3. LLM Providers

Implement provider interface and register with `LLMRouter`:

```python
class MyProvider:
    async def chat(self, messages: List[Dict], **kwargs) -> str:
        pass
    
    async def stream_chat(self, messages: List[Dict], **kwargs):
        pass  # yields tokens
```

Registration: `llm_router.register_provider("my_provider", instance, is_default=False)`

### 4. Knowledge Providers

Implement embedding provider:

```python
class MyEmbeddingProvider:
    async def embed_text(self, text: str) -> List[float]:
        pass
```

Wired via: `EmbeddingsManager(provider=MyEmbeddingProvider())`

### 5. Event Subscribers

Subscribe to EventBus topics:

```python
event_bus.subscribe("conversation.completed", my_handler, priority=100)
```

### 6. API Routes

Add routes to the FastAPI `router` in `app/api/routes.py`:

```python
@router.post("/my_endpoint")
async def my_endpoint(orchestrator = Depends(get_orchestrator)):
    pass
```

### 7. Gateway Routes

Add proxy routes in `services/gateway/src/app.js`:

```javascript
app.use('/my_route', createProxyMiddleware({ target: PYTHON_API_BASE }));
```

### 8. Workflow Step Types

Add new step type handler in `WorkflowWorkerAgent.execute_task()` in `app/workflow_runtime/worker_agent.py`:

```python
if step.type == "my_new_type":
    result = await self._handle_my_type(step)
```

---

## Public Interfaces

### Python API Endpoints

| Endpoint | Method | Handler | Description |
|----------|--------|---------|-------------|
| `/ask` | POST | `FridayOrchestrator.process_query()` | Non-streaming query |
| `/ask/stream` | POST | `FridayOrchestrator.process_stream()` | Streaming query (SSE) |
| `/health` | GET | Kernel health check | All subsystem health |
| `/missions` | CRUD | `MissionManager` | Mission lifecycle |
| `/workflows` | CRUD | Legacy `WorkflowEngine` | Legacy workflow CRUD |
| `/knowledge` | CRUD | `KnowledgeEngine` | Knowledge index/query |
| `/sessions` | CRUD | `MemoryManager` | Session management |
| `/kernel` | GET | Kernel state | Kernel status info |

### Key Public Classes

| Class | Module | Role |
|-------|--------|------|
| `FridayKernel` | `app.kernel.kernel` | Singleton system kernel |
| `FridayServiceContainer` | `app.kernel.container` | DI container |
| `EventBus` | `app.events.bus` | Pub/sub event system |
| `FridayOrchestrator` | `app.friday.orchestrator` | Request orchestrator |
| `BaseTool` | `app.tools.base_tool` | Tool interface |
| `BaseAgent` | `app.agents.base` | Agent interface |
| `ToolRegistry` | `app.friday.tool_registry` | Tool registration |
| `AgentRegistry` | `app.agents.registry` | Agent registration |
| `LLMRouter` | `app.llm.router` | LLM provider routing |
| `MemoryEngine` | `app.memory.engine` | Memory persistence |
| `KnowledgeEngine` | `app.friday.knowledge_engine` | Knowledge retrieval |
| `WorkflowRuntimeManager` | `app.workflow_runtime.manager` | Workflow execution |
| `Planner` | `app.friday.planner` | Plan generation |

### Key Events (EventBus Topics)

| Event Class | Topic | Published By |
|-------------|-------|-------------|
| `ConversationReceived` | `conversation.received` | `FridayOrchestrator` |
| `ConversationCompleted` | `conversation.completed` | `FridayOrchestrator` |
| `ToolCompleted` | `tool.completed` | `ToolEngine` |
| `MemoryUpdated` | `memory.updated` | `MemoryManager` |
| `WorkflowStarted` | `workflow.started` | `WorkflowRuntimeManager` |
| `WorkflowCompleted` | `workflow.completed` | `WorkflowRuntimeManager` |
| `WorkflowFailed` | `workflow.failed` | `WorkflowRuntimeManager` |
| `WorkflowCancelled` | `workflow.cancelled` | `WorkflowRuntimeManager` |
| `WorkflowPaused` | `workflow.paused` | `WorkflowRuntimeManager` |
| `WorkflowResumed` | `workflow.resumed` | `WorkflowRuntimeManager` |
| `AgentTaskCompleted` | `agent.task.completed` | `AgentCoordinator` |
| `AgentTaskFailed` | `agent.task.failed` | `AgentCoordinator` |
| `AgentTaskDelegated` | `agent.task.delegated` | `AgentCoordinator` |
| `KernelBooting` | `kernel.booting` | `FridayKernel` |
| `KernelReady` | `kernel.ready` | `FridayKernel` |
| `KernelShutdown` | `kernel.shutdown` | `FridayKernel` |

---

## Project Layout

```
services/friday-api/
    app/
        kernel/          # Kernel, boot, DI container, lifecycle, module registry
            kernel.py
            boot.py
            container.py
            lifecycle_manager.py
            module_registry.py
            module.py
            capability.py
            health_monitor.py
            config_system.py
            ...
        events/          # EventBus, event classes
            bus.py
            events.py
        friday/           # Orchestrator, planner, tool engine, knowledge engine
            orchestrator.py
            planner.py
            planner_engine.py
            tool_engine.py
            tool_registry.py
            tool_resolver.py
            knowledge_engine.py
            knowledge_document.py
            knowledge_retriever.py
            knowledge_context.py
            knowledge_embeddings.py
            vectordb.py
            retrieval.py
            intent.py
            prompt_manager.py
            executor.py
            plan_adapter.py
            response.py
            context.py
        memory/          # Memory engine, store, manager
            engine.py
            manager.py
            store.py
            conversation.py
            schema.py
            serializer.py
            retriever.py
            embeddings.py
        agents/          # Multi-agent runtime
            base.py
            coordinator.py
            registry.py
            bus.py
            scheduler.py
            telemetry.py
            context.py
        tools/           # Tool implementations
            base_tool.py
            filesystem.py
            terminal.py
            browser.py
            clipboard.py
            open_app.py
            desktop_tools.py
            knowledge_search.py
            tool_resolver.py
        workflow_runtime/ # Workflow runtime (v1.0)
            manager.py
            executor.py
            models.py
            persistence.py
            checkpoints.py
            worker_agent.py
            scheduler_bridge.py
            events.py
        workflow/        # Legacy workflow engine (v0.x)
            engine.py
            history.py
        llm/             # LLM router, Gemini adapter
            router.py
            gemini.py
        missions/        # Mission manager
            mission_manager.py
            mission_history.py
        scheduler/       # Time-based scheduler
            scheduler.py
        desktop/         # Desktop controller, automation
            controller.py
            automation.py
        api/             # FastAPI route definitions
            routes.py
            sessions.py
            knowledge.py
            workflows.py
            missions.py
        core/            # Config, dependencies
            config.py
            dependencies.py
        models/          # Pydantic schemas
            schemas.py
    tests/               # Test suite (181 tests)
    main.py              # FastAPI app entrypoint

services/gateway/
    src/
        controllers/
            sessionController.js
            chatController.js
        app.js           # Express app
        server.js        # HTTP/WS server

apps/desktop/
    src/
        store/
            useSystemStore.ts
        features/
            assistant/
                pages/
                    AssistantPage.tsx
        types/
            index.ts

src/                     # Legacy/JS AI providers
    ai/
        providers/
            GeminiProvider.js
```
