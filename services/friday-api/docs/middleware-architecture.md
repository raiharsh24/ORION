# Execution Middleware Architecture

## Design

Middleware hooks provide extension points before and after every pipeline stage.
They enable plugins, metrics, logging, and custom behavior to be injected without
modifying the core execution flow.

## Middleware Interface

Each middleware extends `ExecutionMiddleware` and can override any combination
of hooks:

```python
class ExecutionMiddleware:
    async def before_intent(self, ctx): ...
    async def after_intent(self, ctx): ...
    async def before_planning(self, ctx): ...
    async def after_planning(self, ctx): ...
    async def before_memory(self, ctx): ...
    async def after_memory(self, ctx): ...
    async def before_tool_selection(self, ctx): ...
    async def after_tool_selection(self, ctx): ...
    async def before_execution(self, ctx): ...
    async def after_execution(self, ctx): ...
    async def before_enrichment(self, ctx): ...
    async def after_enrichment(self, ctx): ...
    async def before_llm(self, ctx): ...
    async def after_llm(self, ctx): ...
    async def before_response(self, ctx): ...
    async def after_response(self, ctx): ...
    async def on_error(self, ctx, stage, error): ...
    async def on_cancel(self, ctx): ...
```

## Hook Order

```
before_intent → [INTENT] → after_intent
before_planning → [PLANNING] → after_planning
before_memory → [MEMORY] → after_memory
before_tool_selection → [TOOL_SELECTION] → after_tool_selection
before_execution → [EXECUTION] → after_execution
before_enrichment → [ENRICHMENT] → after_enrichment
before_llm → [LLM] → after_llm
before_response → [RESPONSE] → after_response

[on_error] — called on any stage failure
[on_cancel] — called on cancellation
```

## Built-in Middleware

### LoggingMiddleware
- Logs entry/exit of every stage with execution ID and key data.
- Registered by default.

### MetricsMiddleware  
- Records per-stage latency and errors to ExecutionMetrics.
- Registered by default.

### PluginHookMiddleware
- Calls lifecycle hooks on loaded plugins before/after planning, execution, and response.
- Loaded plugins must implement the hook method (e.g., `before_planning(ctx)`).
- Each hook call is wrapped in PluginRuntime.execute() for sandboxed execution.
- 5s timeout per plugin hook call.
- Silently skips plugins that don't implement the hook.

### MemoryUpdateMiddleware
- Updates session state after execution (tool_used, tool_output).

## Custom Middleware

Create a new middleware class and add it to the engine:

```python
from app.execution import ExecutionMiddleware

class MyMiddleware(ExecutionMiddleware):
    async def before_llm(self, ctx):
        # Inject custom context into the prompt
        ctx.metadata["custom_data"] = fetch_data()

engine = UnifiedExecutionEngine(...)
engine.add_middleware(MyMiddleware())
```

## MiddlewareChain

The chain maintains an ordered list of middlewares. Each hook iterates through
all middlewares in registration order, calling the corresponding method if
defined.

```python
chain = MiddlewareChain()
chain.add(LoggingMiddleware())
chain.add(MetricsMiddleware(metrics))
chain.add(PluginHookMiddleware(plugin_runtime))
```

## Security

- Middleware runs inside the execution context and has access to the full
  ExecutionContext (including prompts, responses, tool output).
- Plugin hooks execute inside the PluginRuntime sandbox with resource quotas.
- Only explicitly registered middlewares are added to the chain.
