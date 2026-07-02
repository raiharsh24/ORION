# Capability Engine Architecture

## Design Principles

1. **Abstraction, not execution** — Capabilities define *what* FRIDAY can do;
   *how* is delegated to ToolSelectionEngine and ToolExecutionEngine.
2. **Never bypass layers** — Resolution always flows through
   CapabilityResolver → ToolSelectionEngine → ToolExecutionEngine.
3. **Deterministic resolution** — No LLM or AI in capability lookup;
   matching is by id, alias, or category.
4. **Versioned definitions** — Each capability carries a semantic version
   for compatibility tracking.
5. **Health-aware** — Every capability tracks execution success/failure,
   availability, and dependency status.

## Package Structure

```
app/capabilities/
├── __init__.py       # Public API exports
├── base.py           # Core models: CapabilityDefinition, CapabilityCategory,
│                     #   CapabilityStatus, CapabilityDependency, CapabilityHealth,
│                     #   CapabilityPermission, CapabilityResult, CapabilityResolution
├── events.py         # 5 FridayEvent subtypes
├── metadata.py       # build_metadata helper
├── health.py         # CapabilityEngineHealth aggregate
├── registry.py       # CapabilityRegistry — registration, discovery, health
├── resolver.py       # CapabilityResolver — resolution with dependency checking
├── defaults.py       # 11 predefined capability definitions
└── capability.py     # Legacy BaseCapability ABC (maintained for backward compat)
```

## Core Data Flow

```
register(CapabilityDefinition)
  │
  ├─ Store in _definitions dict
  ├─ Index aliases in _alias_map
  ├─ Create default CapabilityPermission
  ├─ Create initial CapabilityHealth
  └─ Publish CapabilityRegistered
       │
resolve(capability_id)
  │
  ├─ resolve_alias() — check id → check alias
  ├─ status check — must be ACTIVE
  ├─ dependency check — all non-optional deps must be registered + active
  ├─ collect transitive dependencies
  ├─ record resolution
  ├─ publish CapabilityResolved
  └─ return CapabilityResolution with tool_ids + resolved_deps
       │
resolve_with_selection(capability_id, context)
  │
  ├─ resolve() first
  ├─ if errors → return ToolSelectionResult(errors)
  ├─ add capability_id to context.required_capabilities
  └─ await ToolSelectionEngine.select(context)
```

## Resolution Chain

```
CapabilityResolver.resolve("knowledge_retrieval")
  │
  ├─ Lookup → CapabilityDefinition(id="knowledge_retrieval", ...)
  ├─ Status check → ACTIVE ✓
  ├─ Dependency check → memory_access is ACTIVE ✓
  ├─ Collect transitive deps → ["memory_access"]
  ├─ Resolve tools → ["query_knowledge", "retrieve_documents"]
  ├─ Publish CapabilityResolved
  └─ Return CapabilityResolution
       │
       v
CapabilityResolver.resolve_with_selection("knowledge_retrieval", ctx)
  ├─ resolve("knowledge_retrieval") → CapabilityResolution
  ├─ ctx.required_capabilities = ["knowledge_retrieval"]
  └─ ToolSelectionEngine.select(ctx) → ToolSelectionResult
```

## Dependency Resolution

Dependencies are checked transitively:

```
cap_c
  └─ dep: cap_b (required)
       └─ dep: cap_a (required)

resolve("cap_c"):
  ✓ cap_b is registered + ACTIVE
  ✓ cap_a is registered + ACTIVE (transitive)
  resolved_dependencies = ["cap_b", "cap_a"]
```

Optional dependencies that are missing do NOT block resolution.

## Health Model

```
CapabilityHealth per capability:
  ├─ availability: bool
  ├─ status: "unknown" | "healthy" | "degraded" | "unhealthy" | "available" | "unavailable"
  ├─ execution_success_count / execution_failure_count
  ├─ last_execution: datetime
  └─ version: str

Status transitions:
  - On register → status = definition.status ("active")
  - On successful execution → "healthy"
  - On any failure → "degraded"
  - On >50% failure rate → "unhealthy"
  - On set_availability(False) → "unavailable"
```

## Registry Performance

| Operation | Complexity | Notes |
|---|---|---|
| `register` | O(1) | Dict insert + alias indexing |
| `get` | O(1) | Dict lookup |
| `resolve_alias` | O(1) | Dict lookup (id) → Dict lookup (alias) |
| `unregister` | O(a) | a = alias count |
| `search` | O(n × (1 + a + t)) | n = caps, a = aliases, t = tags |
| `list_by_category` | O(n) | Filter pass |
| `aggregate_health` | O(n) | Summation pass |
| `get_dependency_graph` | O(n) | Build adjacency list |

## Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| `CapabilityRegistry` | `EventBus` (optional) | Event publishing |
| `CapabilityResolver` | `CapabilityRegistry` | Capability lookup |
| `CapabilityResolver` | `ToolSelectionEngine` | Tool selection delegation |
| `CapabilityResolver` | `EventBus` (optional) | Event publishing |
