# Capability Engine Walkthrough

## Overview

The Capability Engine provides a stable abstraction layer between
missions/workflows and low-level tool execution. **Capabilities** represent
*what* FRIDAY can do, while **Tool Selection** and **Tool Execution**
determine *how* it is accomplished.

## Architecture Layers

```
Mission
  └─ Workflow
       └─ Capability Engine
            ├─ CapabilityRegistry   (registration, discovery, health)
            └─ CapabilityResolver   (resolution → ToolSelectionEngine)
                 └─ ToolSelectionEngine
                      └─ ToolExecutionEngine
```

The Capability Engine **never bypasses** existing engines. Resolution always
delegates to ToolSelectionEngine.

## Core Models

### CapabilityDefinition
| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier |
| `name` | `str` | Human-readable name |
| `description` | `str` | What this capability does |
| `category` | `CapabilityCategory` | Grouping category |
| `version` | `str` | Semantic version |
| `status` | `CapabilityStatus` | ACTIVE / INACTIVE / DEPRECATED / DISABLED |
| `aliases` | `List[str]` | Alternative names for lookup |
| `tool_ids` | `List[str]` | Primary tools that implement this capability |
| `recommended_tool_ids` | `List[str]` | Fallback/preferred tools |
| `dependencies` | `List[CapabilityDependency]` | Required capabilities |
| `permission_level` | `str` | Minimum permission level |

### CapabilityCategory
```
WEB_SEARCH, FILE_ANALYSIS, DESKTOP_AUTOMATION, KNOWLEDGE_RETRIEVAL,
MEMORY_ACCESS, VISION, VOICE, TERMINAL, WORKFLOW_CONTROL, BROWSER,
CODE_EXECUTION, SYSTEM, COMMUNICATION, DATA_PROCESSING, MONITORING, CUSTOM
```

## Quick Start

```python
from app.capabilities.registry import CapabilityRegistry
from app.capabilities.base import (
    CapabilityDefinition, CapabilityCategory,
)

registry = CapabilityRegistry(event_bus=event_bus)

# Register a custom capability
registry.register(CapabilityDefinition(
    id="data_export",
    name="Data Export",
    description="Export data to external formats",
    category=CapabilityCategory.DATA_PROCESSING,
    version="1.0.0",
    aliases=["export", "csv_export"],
    tool_ids=["csv_writer", "json_serializer"],
))

# Lookup by alias
cap = registry.resolve_alias("export")
print(cap.name)  # "Data Export"

# List all capabilities in a category
from app.capabilities.base import CapabilityCategory
web_caps = registry.list_by_category(CapabilityCategory.WEB_SEARCH)
```

## Default Capabilities

The engine ships with 11 predefined capability definitions:

| Capability | Category | Aliases |
|---|---|---|
| `web_search` | WEB_SEARCH | search, internet_search, web |
| `file_analysis` | FILE_ANALYSIS | file_read, file_analyze, read_file |
| `desktop_automation` | DESKTOP_AUTOMATION | desktop, gui, ui_control |
| `knowledge_retrieval` | KNOWLEDGE_RETRIEVAL | knowledge, kb, knowledge_base |
| `memory_access` | MEMORY_ACCESS | memory, memories, long_term_memory |
| `vision` | VISION | image, screenshot, visual, ocr |
| `voice` | VOICE | speech, audio, speak, listen |
| `terminal` | TERMINAL | shell, command, bash |
| `workflow_control` | WORKFLOW_CONTROL | workflow, pipeline, orchestrate |
| `browser` | BROWSER | web_browser, internet, webpage |
| `code_execution` | CODE_EXECUTION | code, programming, execute |

Registered automatically during kernel boot (Step 7g).

## Resolution

```python
from app.capabilities.base import ToolSelectionContext

# Simple resolution (finds capability, checks deps, returns metadata)
resolution = resolver.resolve("web_search")
print(resolution.resolved_tool_ids)  # ["web_search", "browser_navigate"]
print(resolution.resolved_dependencies)  # []

# Resolution with tool selection (delegates to ToolSelectionEngine)
ctx = ToolSelectionContext()
result = await resolver.resolve_with_selection("file_analysis", ctx)
# result is a ToolSelectionResult from ToolSelectionEngine
```

## Dependency Graph

```python
# Get the full dependency graph
graph = registry.get_dependency_graph()
# {"knowledge_retrieval": ["memory_access"], "browser": ["web_search"], ...}

# Get dependencies of a specific capability
deps = registry.get_dependencies("browser")
# [CapabilityDependency(capability_id="web_search", optional=True)]
```

## Health Tracking

```python
# Per-capability health
health = registry.get_health("terminal")
print(health.availability)       # True
print(health.execution_success_count)  # ...

# Update health on execution
registry.update_health("terminal", success=True, duration_ms=150.0)

# Mark unavailable
registry.set_availability("terminal", False, "Shell access restricted")

# Aggregate engine health
engine_health = registry.aggregate_health()
print(engine_health.total_capabilities)     # 11
print(engine_health.active_capabilities)    # 11
print(engine_health.success_rate)           # 100.0
```

## Permissions

```python
from app.capabilities.base import CapabilityPermission

# Permission checked during registration
perm = registry.get_permission("terminal")
print(perm.required_level)  # "elevated"

# Custom permission
registry.register(
    definition=CapabilityDefinition(id="admin_tool", ...),
    permission=CapabilityPermission(
        capability_id="admin_tool",
        required_level="admin",
        allowed_roles=["admin", "superuser"],
    ),
)
```

## Events

| Event | Trigger |
|---|---|
| `CapabilityRegistered` | capability registered |
| `CapabilityRemoved` | capability unregistered |
| `CapabilityResolved` | resolution completed |
| `CapabilityHealthChanged` | health status transition |
| `CapabilityExecuted` | execution completed |

## Search & Discovery

```python
# Search by id, name, description, alias, or tag
results = registry.search("search")
# Returns web_search, browser, etc.

# List all as metadata (lighter weight)
metas = registry.list_metadata()
for m in metas:
    print(f"{m.name} v{m.version} - {m.tool_count} tools")

# Filter by status
active = registry.list_by_status(CapabilityStatus.ACTIVE)
deprecated = registry.list_by_status(CapabilityStatus.DEPRECATED)
```
