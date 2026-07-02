# Universal Tool Registry — Walkthrough

## Overview

The Universal Tool Registry (`app/tools/registry.py`) is a unified capability
registry that manages every executable tool in FRIDAY. It serves as the single
source of truth for all capabilities available to the intelligence layer.

## Key Concepts

### ToolDefinition

Every tool is described by a `ToolDefinition` dataclass:

| Field                    | Description                                      |
|--------------------------|--------------------------------------------------|
| `id`                     | Unique identifier                                |
| `name`                   | Human-readable name                              |
| `description`            | What the tool does                               |
| `category`               | `ToolCategory` enum (19 categories)              |
| `version`               | Semver string                                    |
| `author`                | Creator name                                     |
| `input_schema`          | JSON Schema for expected inputs                  |
| `output_schema`         | JSON Schema for returned outputs                 |
| `permission_level`       | `PermissionLevel` (user/elevated/admin/system)   |
| `estimated_cost`        | Computational cost estimate                      |
| `estimated_latency_ms`  | Expected execution latency                       |
| `supports_streaming`    | Can stream results                               |
| `supports_cancellation` | Can be cancelled mid-execution                   |
| `supports_parallel_execution` | Can run concurrently with other tools      |
| `health`                | `ToolHealth` status with error/success counts    |
| `dependencies`          | List of `ToolDependency` references              |
| `tags`                  | Arbitrary search tags                            |

### ToolCategory (19 categories)

filesystem, browser, terminal, clipboard, desktop, git, docker, python,
memory, knowledge, workflow, mission, email, calendar, ocr, camera,
microphone, llm, custom_plugins

### PermissionLevel (4 levels)

user → elevated → admin → system (hierarchical; higher implies lower)

## Registry Operations

### Registration

```python
registry.register(ToolDefinition(
    id="file_read",
    name="Read File",
    description="Reads a file from the filesystem",
    category=ToolCategory.FILESYSTEM,
    permission_level=PermissionLevel.USER,
    tags=["read", "file"],
))
```

- Publishes `ToolRegistered` event.
- If a tool with the same `id` already exists, it is replaced (old index entries
  cleaned up first).

### Removal

```python
registry.remove("file_read", reason="deprecated")
```

- Publishes `ToolRemoved` event.
- Removes from category and tag indexes.

### Discovery

```python
# By exact ID
tool = registry.get("file_read")

# List all
all_tools = registry.list_tools()

# Search by name, description, or both
registry.search_by_name("read")
registry.search_by_description("file")
registry.search_by_capability("read")

# By category
fs_tools = registry.get_by_category(ToolCategory.FILESYSTEM)

# By tags (AND intersection)
registry.search_by_tags(["read", "file"])
```

### Health

```python
# Per-tool health
health = registry.get_tool_health("file_read")

# Update health (publishes ToolHealthChanged on status change)
registry.update_tool_health("file_read", ToolHealth(status="healthy"))

# Registry-wide health snapshot
h = registry.registry_health()
# h.status, h.registered_tools, h.healthy_tools, h.unavailable_tools
```

### Dependencies

```python
# Tools this tool depends on
deps = registry.get_dependencies("file_read")

# Tools that depend on this tool
dependents = registry.get_dependents("file_read")
```

### Permissions

```python
# Get permission level for a tool
level = registry.get_permission("file_read")

# List all tools at a given permission level
admin_tools = registry.get_tools_by_permission(PermissionLevel.ADMIN)

# Check if a user has sufficient permission
if registry.check_permission("file_read", PermissionLevel.USER):
    ...
```

## Events

| Event               | When Published          | Data                          |
|---------------------|-------------------------|-------------------------------|
| `ToolRegistered`    | Tool is registered      | tool_id, name, category, ...  |
| `ToolRemoved`       | Tool is removed         | tool_id, name, reason         |
| `ToolHealthChanged` | Health status changes   | tool_id, name, status, msg    |

Events implement `FridayEvent` and are published via `EventBus`.

## Kernel Integration

The registry is registered as a singleton in Step 3n of `boot.py`:

- **DI key:** `"universal_tool_registry"`
- **Module:** `"universal_tool_registry"` v1.0.0, depends on `event_bus`
- **Capability:** `"UniversalToolRegistry"`

```python
from app.tools.registry import ToolRegistry as UniversalToolRegistry
universal_tool_registry = UniversalToolRegistry(event_bus=event_bus)
container.register_singleton("universal_tool_registry", universal_tool_registry)
```

## Architecture

```
┌─────────────────────────────────────────────┐
│               ToolRegistry                   │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Tools   │ │Category  │ │   Tag Index   │  │
│  │  Dict   │ │  Index   │ │ (tag→set)    │  │
│  └─────────┘ └──────────┘ └──────────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌──────────────┐  │
│  │Permission│ │  Health  │ │ Event Pub    │  │
│  │Registry  │ │  Tracker │ │ (EventBus)   │  │
│  └─────────┘ └──────────┘ └──────────────┘  │
└─────────────────────────────────────────────┘
         │
         ▼
   EventBus → ToolRegistered / ToolRemoved / ToolHealthChanged
```

## File Layout

```
app/tools/
├── __init__.py        # Package exports (new + legacy tool classes)
├── base.py            # ToolDefinition, ToolCategory, PermissionLevel, etc.
├── metadata.py        # ToolMetadata (view model from ToolDefinition)
├── permissions.py     # PermissionRegistry (internal permission store)
├── events.py          # ToolRegistered, ToolRemoved, ToolHealthChanged
├── health.py          # ToolRegistryHealth (aggregate health snapshot)
├── registry.py        # ToolRegistry (main class)
```

## Test Coverage

- **46 tests** in `tests/test_tools_registry.py`
- Covers: model defaults, metadata conversion, permission hierarchy, registry
  CRUD, event publishing, search by name/description/capability/category/tags,
  health tracking, dependency graph, edge cases (re-registration, same ID
  with different category, event errors, no event bus)
- Full regression: **948 tests pass** with zero regressions.
