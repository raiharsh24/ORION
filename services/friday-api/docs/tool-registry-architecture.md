# Universal Tool Registry — Architecture

## Design Goals

1. **Single source of truth** — every executable capability has one entry.
2. **Discovery-first** — search by name, description, category, or tags.
3. **Permission-aware** — hierarchical permission model (user → system).
4. **Health-aware** — each tool tracks execution health; registry provides
   aggregate health snapshot.
5. **Pluggable** — new tools register at boot or runtime; no code changes
   needed.
6. **Event-driven** — registration and health changes propagate via EventBus.

## Data Model

```
ToolDefinition
├── identity: id, name, version, author
├── classification: category, tags, permission_level
├── interface: input_schema, output_schema
├── perf: estimated_cost, estimated_latency_ms
├── capabilities: streaming, cancellation, parallel
├── health: ToolHealth (status, counts, avg latency)
└── deps: List[ToolDependency]

ToolMetadata (derived view, no input/output schemas)
    Used for lightweight discovery without exposing schemas.
```

## Registry Architecture

```
                    ┌──────────────────────┐
                    │     ToolRegistry      │
                    ├──────────────────────┤
                    │  _tools: Dict[str,   │
                    │    ToolDefinition]   │
                    │                      │
                    │  _category_index:    │
                    │    Dict[Category,Set]│
                    │                      │
                    │  _tag_index:         │
                    │    Dict[str, Set]    │
                    │                      │
                    │  PermissionRegistry  │
                    │  EventBus (optional) │
                    └──────┬───────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ToolRegistered  ToolRemoved  ToolHealthChanged
              │            │            │
              └────────────┼────────────┘
                           ▼
                      EventBus
```

### Indexes

- **Category Index**: `ToolCategory → Set[tool_id]` — O(1) lookup by category
- **Tag Index**: `tag_lower → Set[tool_id]` — AND-intersection for multi-tag search
- Both indexes are maintained on `register()` and `remove()`, and cleaned up
  on re-registration.

### Permission Model

```
USER < ELEVATED < ADMIN < SYSTEM
```

`check_permission(tool_id, required)` returns `True` if the tool's level
is >= the required level in the hierarchy. This allows a tool at SYSTEM level
to be callable by USER, ADMIN, or SYSTEM callers.

## Integration Points

| Component           | Integration                                  |
|---------------------|----------------------------------------------|
| `boot.py`           | Step 3n: DI singleton + module + capability  |
| `health.py`         | `universal_tool_registry` subsystem health   |
| `EventBus`          | Publishes 3 event types                      |
| `kernel.py`         | Health check reads `registry_health()`       |

## Event Flow

```
register(tool) → _index_tool → publish(ToolRegistered)
                                        │
                                   EventBus delivers to
                                   subscribers (logging, UI, etc.)

update_health(id, h) → if status changed → publish(ToolHealthChanged)

remove(id) → _deindex_tool → publish(ToolRemoved)
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate `ToolDefinition` vs `ToolMetadata` | Metadata is a lightweight view without schemas for fast browsing |
| AND intersection for tags | More precise filtering; OR can be done by multiple calls |
| Permission stored on each tool | Enables per-tool auditing and access control |
| Health tracked per-tool, aggregated by registry | Both micro and macro visibility |
| EventBus optional | Graceful degradation when registry is used standalone |
| Category enum, not freeform | Enforces consistent categorization for the intelligence layer |
| Separate `PermissionRegistry` class | Encapsulates hierarchy logic and allows reuse |

## Future Considerations

- Tool **execution** (Phase 6 Sprint 2) — will be implemented separately
- Tool **selection** (Phase 6 Sprint 3) — will use this registry for discovery
- Dynamic tool loading from plugins
- Cached dependency resolution (topological sort for execution ordering)
- Health decay: decrement success counts over time
