# Tool Execution Engine — Architecture

## Design Goals

1. **Deterministic execution** — no LLM, agent, or planning logic.
2. **Failure isolation** — one tool failure never crashes the kernel.
3. **Three execution modes** — sequential, parallel, dependency-aware.
4. **Timeout & cancellation** — global per-call timeout and cooperative cancellation.
5. **Retry support** — configurable retry with delay.
6. **Dual registry bridge** — metadata validation + actual `BaseTool` execution.
7. **Full telemetry** — execution count, failure/timeout/retry counts, average latency.

## Architecture

```
                    ┌──────────────────────────────────────┐
                    │         ToolExecutionEngine           │
                    │                                       │
                    │  execute(selection, mode, ...)        │
                    │    │                                  │
                    │    ├─ _build_contexts()               │
                    │    ├─ ExecutionScheduler.order()      │
                    │    ├─ for each layer:                 │
                    │    │   ├─ check cancellation          │
                    │    │   ├─ sequential or parallel      │
                    │    │   └─ _execute_single() per tool   │
                    │    │       ├─ legacy lookup            │
                    │    │       ├─ universal validate       │
                    │    │       ├─ asyncio.wait_for()       │
                    │    │       └─ retry loop               │
                    │    └─ build_report()                   │
                    │                                       │
                    │  cancel(execution_id)                  │
                    │                                       │
                    │  health() → telemetry                  │
                    └───────┬───────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
       LegacyToolReg   UniversalReg    EventBus
       (BaseTool       (ToolDef        (events)
        instances)      metadata)
```

## Data Model

```
ExecutionContext
├── tool_id: str
├── args: Dict[str, Any]
├── timeout: float (seconds)
├── max_retries: int
├── retry_delay: float
└── priority: int

ExecutedTool
├── tool_id: str
├── status: ExecutionStatus (enum)
├── output: Any
├── error: Optional[str]
├── started_at / completed_at: datetime
├── duration_ms: float
└── retries: int

ToolExecutionResult
├── execution_id: str
├── mode: ExecutionMode
├── results: List[ExecutedTool]
├── report: ExecutionReport
└── status: ExecutionStatus

ExecutionReport
├── total_tools / completed / failed / cancelled / timed_out / skipped
├── total_duration_ms: float
├── parallel_efficiency: float
└── errors: List[str]
```

## Scheduler Topological Sort

```
Input: [ctx_a, ctx_b, ctx_c], deps = {c: [a, b]}

Layer 0: [a, b]          # no deps → parallel
Layer 1: [c]             # deps satisfied → single
```

The scheduler handles:
- Empty dependency maps → all tools in layer 0 (parallel)
- Circular deps → falls back to priority ordering
- Priority sorting within layers

## Registry Bridge

The engine resolves tool execution instances from the **legacy** `app.friday.tool_registry.ToolRegistry` and validates against the **universal** `app.tools.registry.ToolRegistry`:

```
legacy_registry.get("file_read") → BaseTool instance
universal_registry.get("file_read") → ToolDefinition (for validation)
```

If the universal registry is configured and a tool is not found there, the
execution is rejected with FAILED status.

## File Layout

```
app/tool_execution/
├── __init__.py       # Package exports
├── base.py           # Core models: ExecutionContext, ExecutedTool, etc.
├── events.py         # 4 event types
├── result.py         # build_report() utility
├── scheduler.py      # ExecutionScheduler (topological sort)
├── executor.py       # ToolExecutionEngine, CancellationToken
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Layer-based scheduling | Enables safe parallel/dependency-ordered execution |
| Cancellation before per-tool loop | Avoids starting tools that will be immediately cancelled |
| Retry loop inside `_execute_single` | Clean per-tool lifecycle; retries don't affect other tools |
| Dual registry bridge | Leverages existing `BaseTool` instances while validating via new metadata |
| Report built after all results | Single-pass aggregation with parallel efficiency metric |
| Events per tool, not per layer | Granular observability; one event per tool execution |
| `global_timeout` + per-tool timeout | Flexible: global safety net + tool-specific limits |
