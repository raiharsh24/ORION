# Tool Execution Engine — Walkthrough

## Overview

The Tool Execution Engine (`app/tool_execution/executor.py`) executes selected
tools deterministically. It bridges the Universal Tool Registry (metadata)
with the legacy `BaseTool` execution instances and supports sequential,
parallel, and dependency-aware execution modes with timeout, retry, and
cancellation.

## Input

```python
ToolSelectionResult(
    selected_tools=[SelectedTool(tool=tool_def, score=0.95)],
    ...
)

# Optional overrides:
args_overrides = {"tool_id": {"key": "value"}}
mode = ExecutionMode.PARALLEL
dependency_map = {"tool_b": ["tool_a"]}
global_timeout = 60.0
cancellation_token = CancellationToken()
```

## Output

```python
ToolExecutionResult(
    execution_id="uuid",
    mode=ExecutionMode.SEQUENTIAL,
    results=[
        ExecutedTool(tool_id="read_file", status=COMPLETED,
                     output="content", duration_ms=12.5),
        ExecutedTool(tool_id="write_file", status=FAILED,
                     error="Permission denied", duration_ms=0.3),
    ],
    report=ExecutionReport(
        total_tools=2, completed=1, failed=1,
        total_duration_ms=15.2,
        errors=["Permission denied"],
    ),
    status=COMPLETED,
)
```

## Execution Modes

| Mode               | Description                                      |
|--------------------|--------------------------------------------------|
| `SEQUENTIAL`       | Execute one tool at a time, in order             |
| `PARALLEL`         | Execute all tools concurrently                   |
| `DEPENDENCY_AWARE` | Topological sort; parallel within each layer     |

## Execution Flow

```
Selection Result
     │
     ▼
Build Contexts
  • Map each SelectedTool to ExecutionContext
  • Apply args overrides
  • Compute timeout from estimated_latency
     │
     ▼
Schedule Layers
  • Sequential → one tool per layer
  • Parallel → one layer with all tools
  • Dependency-aware → topological sort
     │
     ▼
For Each Layer:
  │
  ├─ Check cancellation ────► Cancelled status + event
  │
  ├─ Sequential layer:
  │     For each context:
  │       └─ _execute_single()
  │            ├─ Lookup BaseTool instance
  │            ├─ Validate against Universal Registry
  │            ├─ asyncio.wait_for(timeout)
  │            ├─ Retry on failure (if configured)
  │            └─ Publish events
  │
  └─ Parallel layer:
        └─ asyncio.gather(_execute_single() for each)
```

## Tool Lifecycle

```
Pending → Running → Completed (on success)
                  → Failed (on exception, retries exhausted)
                  → Timeout (on asyncio.TimeoutError, retries exhausted)
                  → Cancelled (on cancellation token)
                  → Skipped (not reached due to cancellation)
```

## Retry Policy

Each `ExecutionContext` supports:
- `max_retries`: max retry attempts (default 0)
- `retry_delay`: seconds to wait between retries (default 1.0s)
- All error types are retried; timeout errors are tracked separately

## Events

| Event                     | When Published             | Data                                  |
|---------------------------|----------------------------|---------------------------------------|
| `ToolExecutionStarted`    | Layer execution begins     | execution_id, tool_id, mode, total    |
| `ToolExecutionCompleted`  | Tool succeeds              | execution_id, tool_id, duration, output|
| `ToolExecutionFailed`     | Tool fails (retries done)  | execution_id, tool_id, error, retries |
| `ToolExecutionCancelled`  | Tool cancelled             | execution_id, tool_id, reason         |

## Integration

- **DI key:** `"tool_execution_engine"`
- **Boot step:** 7d (after legacy tool registry in Step 7)
- **Module:** `"tool_execution_engine"` v1.0.0, depends on `event_bus`, `tool_registry`, `universal_tool_registry`
- **Capability:** `"ToolExecution"`
- **Health:** `tool_execution_engine` subsystem in `KernelHealth`
