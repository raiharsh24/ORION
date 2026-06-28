# FRIDAY Core v1.0 Developer Guide

How to extend FRIDAY with new tools, agents, LLM providers, memory providers, and workflow nodes.

---

## Table of Contents

1. [Adding New Tools](#adding-new-tools)
2. [Adding New Agents](#adding-new-agents)
3. [Adding New LLM Providers](#adding-new-llm-providers)
4. [Adding New Memory Providers](#adding-new-memory-providers)
5. [Adding New Workflow Node Types](#adding-new-workflow-node-types)
6. [Testing](#testing)

---

## Adding New Tools

### Step 1: Create the tool class

Create a file in `services/friday-api/app/tools/` and implement `BaseTool`:

```python
from typing import Any
from app.tools.base_tool import BaseTool

class MySearchTool(BaseTool):
    name = "my_search"
    description = "Searches an external API for information"

    async def execute(self, query: str, max_results: int = 5) -> str:
        # Your implementation here
        results = await self._call_external_api(query, max_results)
        return results

    def requires_confirmation(self) -> bool:
        return True  # Only if the operation is destructive or external
```

### Step 2: Register with ToolRegistry

In `services/friday-api/app/kernel/boot.py`, after the Tool Engine step:

```python
# Inside BootManager.run_boot_sequence(), after tool_engine registration
from app.tools.my_search import MySearchTool
tool_registry.register(MySearchTool())
```

The `tool_registry` variable is imported from `app.core.dependencies` at line 109.

### Step 3: (Optional) Add capability

If the tool exposes a new capability, register it in the `CapabilityRegistry`:

```python
kernel.capability_registry.register_capability(
    name="ExternalSearch",
    module_name="my_search_tool",
    description="External API search capability"
)
```

### Step 4: Test

```python
# Write unit tests in tests/test_tools/
@pytest.mark.asyncio
async def test_my_search_tool():
    tool = MySearchTool()
    result = await tool.execute(query="test")
    assert result is not None
```

### Existing Tool Reference

| Pattern | File | Implementation |
|---------|------|---------------|
| Stateless | `tools/browser.py` | Simple `httpx` call with timeout |
| Stateful init | `tools/clipboard.py` | Platform detection in `__init__` |
| Subprocess | `tools/terminal.py` | `asyncio.create_subprocess_exec` with allow/block lists |
| Delegation | `tools/desktop_tools.py` | Wraps `DesktopController` instance |
| Knowledge | `tools/knowledge_search.py` | Delegates to `RetrievalEngine` |

### Important Rules

- Tools must be **stateless** or thread-safe. The same instance may be called concurrently.
- Destructive operations (file write, command execution) should set `requires_confirmation() → True`.
- Use `asyncio` for all I/O. Blocking calls should use `asyncio.to_thread()`.
- Respect workspace boundaries: use `_safe_resolve()` (from `tools/filesystem.py`) for file operations.
- Add terminal commands to the ALLOWED list in `tools/terminal.py` rather than bypassing the tool.

---

## Adding New Agents

### Step 1: Create the agent class

Create a file in `services/friday-api/app/agents/` and extend `BaseAgent`:

```python
from typing import Any, Optional
from app.agents.base import BaseAgent
from app.agents.models import AgentTask

class MyCustomAgent(BaseAgent):
    def __init__(self, agent_id: str = "my-custom-agent", name: str = "My Custom Agent"):
        super().__init__(agent_id=agent_id, name=name)

    async def execute_task(self, task: AgentTask) -> Any:
        # Access shared context for tools/LLM
        context = self._context

        if task.task_type == "my_type":
            result = await context.execute_tool("my_search", query=task.input)
            return result

        raise ValueError(f"Unknown task type: {task.task_type}")

    async def initialize(self) -> None:
        # Setup resources (connections, clients)
        pass

    async def shutdown(self) -> None:
        # Cleanup resources
        pass
```

### Step 2: Register with AgentRegistry

In `services/friday-api/app/kernel/boot.py`, Step 11 (after agent_coordinator registration):

```python
my_agent = MyCustomAgent()
await agent_registry.register(my_agent)
```

### Step 3: Set shared context

```python
from your_agent_file import MyCustomAgent
my_agent = MyCustomAgent()
await agent_registry.register(my_agent)
my_agent.set_context(shared_context)  # Required for tool execution access
```

### Step 4: Wire into workflow (optional)

If the agent should handle workflow steps, add a handler in `WorkflowWorkerAgent`:

In `services/friday-api/app/workflow_runtime/worker_agent.py`:

```python
if step.type == "my_custom":
    agent_task = AgentTask(
        task_id=str(uuid.uuid4()),
        task_type="my_type",
        input=step.params,
    )
    result = await self._coordinator.delegate(agent_task)
```

### Agent Lifecycle

| Hook | Called when | Override to |
|------|------------|-------------|
| `initialize()` | Kernel boot | Open connections, load config |
| `start()` | After all initialized | Start background loops |
| `execute_task(task)` | AgentCoordinator delegates | Handle the task |
| `cancel_task(task_id)` | User cancels | Abort in-flight work |
| `shutdown()` | Kernel shutdown | Close connections, save state |

### Agent API

Agents interact with the system through `SharedContext`:

```python
class SharedContext:
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a registered tool."""

    async def query_knowledge(self, query: str, **kwargs) -> str:
        """Query the knowledge base."""

    def set(self, key: str, value: Any) -> None:
        """Store shared state."""

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve shared state."""
```

---

## Adding New LLM Providers

### Step 1: Create the provider

The Python side (`app/llm/`) routes to adapters. Create an adapter implementing the expected interface:

```python
# services/friday-api/app/llm/anthropic.py
from typing import List, Dict, AsyncGenerator

class AnthropicAdapter:
    def __init__(self, api_key: str, model_name: str = "claude-3"):
        self._api_key = api_key
        self._model_name = model_name

    async def chat(self, messages: List[Dict], **kwargs) -> str:
        # Return complete response string
        pass

    async def stream_chat(self, messages: List[Dict], **kwargs) -> AsyncGenerator[str, None]:
        # Yield tokens
        pass
```

For the Node.js side (`src/ai/providers/`), implement the JavaScript interface:

```javascript
// src/ai/providers/AnthropicProvider.js
export class AnthropicProvider {
    constructor(config) {
        this.apiKey = config.apiKey;
    }

    async chat(messages, options) {
        // Return { content: "response" }
    }

    async streamChat(messages, options) {
        // Yield tokens via async generator
    }
}
```

### Step 2: Register with LLMRouter

In `services/friday-api/app/kernel/boot.py`, Step 10b:

```python
from app.llm.anthropic import AnthropicAdapter

anthropic_adapter = AnthropicAdapter(
    api_key=config.api_keys.get("anthropic_api_key"),
    model_name="claude-3"
)
llm_router.register_provider("anthropic", anthropic_adapter, is_default=False)
```

### Step 3: Add configuration

Extend `FridayKernelConfig` in `services/friday-api/app/kernel/config.py`:

```python
# Add to api_keys section
anthropic_api_key: str = ""
```

### Step 4: Test

```python
@pytest.mark.asyncio
async def test_anthropic_provider():
    provider = AnthropicAdapter(api_key="test-key")
    result = await provider.chat([{"role": "user", "content": "Hello"}])
    # Mock the API response
    assert result is not None
```

### Provider Interface Contract

| Method | Input | Output | Required |
|--------|-------|--------|----------|
| `chat(messages, **kwargs)` | `List[Dict]` with `role`/`content` | `str` | Yes |
| `stream_chat(messages, **kwargs)` | Same as above | `AsyncGenerator[str]` | No (optional) |

Both `chat()` and `stream_chat()` must accept `options.signal` (AbortSignal) for cancellation support.

---

## Adding New Memory Providers

### Step 1: Create the store class

Implement the `MemoryStore` interface from `app/memory/store.py`:

```python
from app.memory.store import MemoryStore

class PostgresMemoryStore(MemoryStore):
    """PostgreSQL-backed memory store."""

    def __init__(self, connection_string: str):
        self._conn_string = connection_string
        self._pool = None

    async def initialize(self) -> None:
        import asyncpg
        self._pool = await asyncpg.create_pool(self._conn_string)

    async def get(self, key: str) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM memory WHERE key = $1", key
            )
            return dict(row["data"]) if row else None

    async def put(self, key: str, value: Dict) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO memory (key, data) VALUES ($1, $2) "
                "ON CONFLICT (key) DO UPDATE SET data = $2",
                key, json.dumps(value)
            )

    async def delete(self, key: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM memory WHERE key = $1", key)

    async def save(self) -> None:
        pass  # Real-time persistence
```

### Step 2: Wire into MemoryEngine

In `services/friday-api/app/memory/engine.py`:

```python
# Inside MemoryEngine.__init__() or initialize()
self._store = PostgresMemoryStore(config.get("database_url"))
await self._store.initialize()
```

Alternatively, switch the store creation in `services/friday-api/app/core/dependencies.py`:

```python
from app.memory.store import PostgresMemoryStore

memory_store = PostgresMemoryStore(connection_string=settings.database_url)
```

### Step 3: Initialize on boot

If your store needs async initialization, call it in `MemoryEngine.initialize()` (which is called by the lifecycle manager during kernel boot).

### MemoryStore Interface

| Method | Args | Returns | Description |
|--------|------|---------|-------------|
| `get(key)` | `str` | `Optional[Dict]` | Retrieve by key |
| `put(key, value)` | `str, Dict` | `None` | Store/update |
| `delete(key)` | `str` | `None` | Remove key |
| `save()` | None | `None` | Flush to durable storage (optional) |

### Existing Implementations

| Store | File | Backend |
|-------|------|---------|
| `InMemoryStore` | `store.py:36` | Python dict (volatile) |
| `JSONStore` | `store.py:68` | JSON file on disk |

---

## Adding New Workflow Node Types

### Step 1: Extend the step type enum

In `services/friday-api/app/workflow_runtime/models.py`:

```python
from enum import Enum

class StepType(str, Enum):
    tool = "tool"
    llm = "llm"
    knowledge = "knowledge"
    condition = "condition"
    delay = "delay"
    mission = "mission"
    notification = "notification"
    agent_task = "agent_task"
    http_request = "http_request"  # NEW
```

### Step 2: Add handler in WorkflowWorkerAgent

In `services/friday-api/app/workflow_runtime/worker_agent.py`:

```python
async def _execute_http_request(self, step: RuntimeStep) -> Dict[str, Any]:
    import httpx
    method = step.params.get("method", "GET")
    url = step.params.get("url")
    headers = step.params.get("headers", {})
    body = step.params.get("body")

    async with httpx.AsyncClient() as client:
        response = await client.request(method, url, headers=headers, json=body)

    return {
        "status": response.status_code,
        "body": response.text[:5000],
        "headers": dict(response.headers),
    }

# In execute_task() method, add the new type:
if step.type == "http_request":
    result = await self._execute_http_request(step)
```

### Step 3: Register in Planner (optional)

If the planner should generate this step type, update the planner logic in `app/friday/planner.py` to emit `http_request` steps when appropriate.

### Step 4: Test

```python
async def test_http_request_step():
    worker = WorkflowWorkerAgent(agent_id="test", name="Test", shared_context=ctx)
    step = RuntimeStep(type="http_request", params={"method": "GET", "url": "https://example.com"})
    result = await worker.execute_task(AgentTask(task_type="http_request", input=None))
    assert "status" in result
```

### Existing Step Types Reference

| Step Type | Handler | Params |
|-----------|---------|--------|
| `tool` | `execute_tool(name, **args)` | `tool_name`, `args` |
| `llm` | `_execute_llm()` | `prompt`, `provider`, `model` |
| `knowledge` | `_execute_knowledge()` | `query`, `max_results` |
| `condition` | `_evaluate_condition()` | `expression` (Python eval) |
| `delay` | `asyncio.sleep()` | `seconds` |
| `mission` | `MissionManager.handle_event()` | `event`, `params` |
| `notification` | `_send_notification()` | `message`, `severity` |
| `agent_task` | `_delegate_to_agent()` | `task_type`, `input` |

---

## Testing

Run the full test suite:

```bash
cd services/friday-api
python3 -m pytest tests/ -x -q
```

Current count: **181 tests, 0 failures**.

### Test Patterns

```python
# Tool test
@pytest.mark.asyncio
async def test_my_tool():
    tool = MyTool()
    result = await tool.execute(param="value")
    assert "expected" in result

# Event subscriber test
@pytest.mark.asyncio
async def test_event_handler():
    bus = EventBus()
    results = []
    bus.subscribe("test.event", lambda e: results.append(e))
    await bus.publish(TestEvent(topic="test.event"))
    assert len(results) == 1

# Agent test
@pytest.mark.asyncio
async def test_my_agent():
    agent = MyAgent(agent_id="test", name="Test")
    task = AgentTask(task_id="1", task_type="my_type", input="data")
    result = await agent.execute_task(task)
    assert result is not None
```
