# Unified Execution Engine — Architecture

## Design

The Unified Execution Engine provides a single orchestration pipeline that chains
all FRIDAY subsystems through a shared execution context with cancellation,
retry, timeout, progress events, and middleware hooks.

### Principle

- **Wrap, don't replace** — every existing subsystem is called via its existing
  interface. No subsystem is redesigned.
- **Shared context** — a single `ExecutionContext` flows through all stages,
  carrying intent, plan, memory, tool output, enrichment, LLM response, and
  metadata.
- **Stage isolation** — each pipeline stage is an independent async handler with
  its own retry, timeout, and error handling.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                UnifiedExecutionEngine (facade)                   │
│  execute()  execute_stream()  check_confirmation()  health()    │
│  cancel()                                                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                        MiddlewareChain                           │
│  before/after intent, planning, memory, tool_selection,          │
│  execution, enrichment, llm, response + on_error + on_cancel     │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐ ┌──────────────┐  │
│  │ Logging  │ │ Metrics  │ │ PluginHooks    │ │ Custom       │  │
│  └──────────┘ └──────────┘ └────────────────┘ └──────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                       ExecutionPipeline                          │
│                                                                  │
│  Stage 1: INTENT        IntentClassifier.classify()             │
│  Stage 2: PLANNING      Planner.plan() → ExecutionPlan          │
│  Stage 3: MEMORY        ConversationMemory retrieval            │
│  Stage 4: SELECTION     ToolSelectionEngine.select()            │
│  Stage 5: EXECUTION     ToolExecutionEngine / ToolExecutor      │
│  Stage 6: ENRICHMENT    CognitiveCore.retrieve_relevant_context │
│  Stage 7: LLM           LLMRouter.get_provider().generate()     │
│  Stage 8: RESPONSE      Build FridayResponse + memory update    │
└─────────────────────────────────────────────────────────────────┘
```

## Execution Flow

```
execute(prompt, session_id, provider)
  │
  ├── 1. Create ExecutionContext (execution_id, cancellation_token)
  │
  ├── 2. Middleware.before_intent()
  ├── 3. IntentClassifier.classify(prompt)
  │     └── [AUTONOMOUS_GOAL] → MissionRuntime.submit_background() → return
  ├── 4. Middleware.after_intent()
  │
  ├── 5. Pipeline.execute(ctx)
  │     │
  │     ├── Planning Stage
  │     │   ├── Middleware.before_planning()
  │     │   ├── Planner.plan(prompt, intent) → ExecutionPlan
  │     │   └── Middleware.after_planning()
  │     │
  │     ├── Memory Stage
  │     │   ├── Middleware.before_memory()
  │     │   ├── ConversationMemory.get_or_create_session()
  │     │   ├── ConversationMemory.get_history_string()
  │     │   └── Middleware.after_memory()
  │     │
  │     ├── Tool Selection Stage
  │     │   ├── Middleware.before_tool_selection()
  │     │   ├── ToolSelectionEngine.select() → SelectedTool[]
  │     │   └── Middleware.after_tool_selection()
  │     │
  │     ├── Execution Stage
  │     │   ├── Middleware.before_execution()
  │     │   ├── ToolExecutionEngine.execute() / ToolExecutor.execute()
  │     │   └── Middleware.after_execution()
  │     │
  │     ├── Enrichment Stage
  │     │   ├── Middleware.before_enrichment()
  │     │   ├── CognitiveCore.retrieve_relevant_context()
  │     │   └── Middleware.after_enrichment()
  │     │
  │     ├── LLM Stage
  │     │   ├── Middleware.before_llm()
  │     │   ├── PromptManager.format_prompt()
  │     │   ├── LLMRouter.get_provider().generate()
  │     │   └── Middleware.after_llm()
  │     │
  │     └── Response Stage
  │         ├── Middleware.before_response()
  │         ├── Memory.add_message() x2
  │         ├── Build FridayResponse with telemetry
  │         └── Middleware.after_response()
  │
  └── 6. Return FridayResponse
```

## Cancellation

- `CancellationToken` is propagated through the entire pipeline.
- Any stage can check `ctx.cancelled` or call `ctx.cancel()`.
- Stage runners check cancellation before each attempt and before execution.
- Pipeline stops at cancellation and raises `CancelledError`.
- Engine catches `CancelledError` and returns a graceful response.

## Retry Policy

| Parameter | Default | Description |
|-----------|---------|-------------|
| max_retries | 3 | Max retry attempts per stage |
| base_delay_ms | 500 | Initial delay before first retry |
| max_delay_ms | 10000 | Maximum delay cap |
| backoff_multiplier | 2.0 | Exponential backoff factor |

## Timeout Policy

| Stage | Default Timeout |
|-------|----------------|
| INTENT | 10s |
| PLANNING | 30s |
| MEMORY | 15s |
| TOOL_SELECTION | 15s |
| EXECUTION | 120s |
| ENRICHMENT | 15s |
| LLM | 60s |

## Key Files

| File | Purpose |
|------|---------|
| `app/execution/engine.py` | UnifiedExecutionEngine facade |
| `app/execution/context.py` | ExecutionContext, CancellationToken, Stage enum |
| `app/execution/config.py` | ExecutionConfig, RetryPolicy, TimeoutPolicy |
| `app/execution/pipeline.py` | ExecutionPipeline, StageRunner |
| `app/execution/middleware.py` | ExecutionMiddleware, MiddlewareChain, LoggingMiddleware |
| `app/execution/middleware_hooks.py` | PluginHookMiddleware, MemoryUpdateMiddleware |
| `app/execution/metrics.py` | ExecutionMetrics |
| `app/execution/events.py` | ExecutionEvent types |
| `app/execution/integration.py` | Kernel wiring factory |

## Comparison: UnifiedEngine vs FridayOrchestrator

| Feature | FridayOrchestrator | UnifiedExecutionEngine |
|---------|-------------------|----------------------|
| Pipeline stages | 6 (implicit) | 8 (explicit with middleware) |
| Execution context | Rebuilt each stage | Shared ExecutionContext |
| Cancellation | Not propagated | Propagated via CancellationToken |
| Retry | None per-stage | Per-stage retry with backoff |
| Timeout | None per-stage | Per-stage configurable timeout |
| Progress events | None | Stage progress events |
| Middleware hooks | None | 18 hooks (before/after × 8 stages + on_error + on_cancel) |
| ToolSelectionEngine | Not used | Optional integration |
| ToolExecutionEngine | Bypassed | Optional integration |
| PluginRuntime | Not called | PluginHookMiddleware |
| Metrics | Basic telemetry only | Per-stage latency, error tracking |
