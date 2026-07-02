# Plugin SDK Architecture

## Design Principles

1. **Local-only** — No marketplace, no cloud agents, no remote downloading.
2. **Stable API** — Plugin developers target a versioned manifest and lifecycle.
3. **Defense in depth** — Manifests are validated, permissions checked,
   dependencies resolved, duplicate IDs rejected.
4. **Deterministic lifecycle** — All transitions are explicit: install → load →
   enable → disable → unload → remove.
5. **Observable** — Every lifecycle transition publishes a FridayEvent.

## Package Structure

```
app/plugins/
├── __init__.py       # Public API exports
├── base.py           # Core models: Plugin, PluginState, PluginVersion,
│                     #   PluginDependency, PluginPermission, PluginHealth,
│                     #   PluginManifest, PluginMetadata
├── manifest.py       # Manifest parsing (JSON → PluginManifest) + validation
├── events.py         # 7 FridayEvent subtypes
├── health.py         # PluginEngineHealth aggregate
├── permissions.py    # PermissionValidator — grant/revoke/validate
├── plugin.py         # PluginWrapper base class (lifecycle hooks)
├── registry.py       # PluginRegistry — CRUD, lifecycle, health, deps
└── loader.py         # PluginLoader — manifest validation, dependency resolution
```

## Core Data Flow

```
load_from_directory("/plugins")
  │
  ├─ Discover subdirectories with plugin.json / manifest.json
  ├─ parse_manifest() → PluginManifest
  ├─ validate_manifest() → errors
  ├─ validate_pre_install() → permission errors
  ├─ PluginRegistry.install() → Plugin
  ├─ resolve_dependencies() → check all deps satisfied
  │    ├─ missing required dep → FAILED, return None
  │    └─ optional dep missing → allowed
  ├─ update_state(LOADED)
  ├─ publish PluginLoaded
  └─ return Plugin

enable_plugin(id)
  ├─ update_state(ENABLED)
  ├─ health.enabled = True
  └─ publish PluginEnabled

disable_plugin(id)
  ├─ update_state(DISABLED)
  ├─ health.enabled = False
  └─ publish PluginDisabled
```

## Lifecycle State Machine

```
                    ┌─────────┐
                    │INSTALLED│ ←── registry.install(manifest)
                    └────┬────┘
                         │ loader.load_plugin() (validate + resolve deps)
                         v
                    ┌─────────┐
                    │  LOADED │ ←── publish PluginLoaded
                    └────┬────┘
                         │ loader.enable_plugin()
                         v
                    ┌─────────┐
                    │ ENABLED │ ←── publish PluginEnabled
                    └────┬────┘
                         │ loader.disable_plugin()
                         v
                    ┌─────────┐
                    │DISABLED │ ←── publish PluginDisabled
                    └────┬────┘
                         │ loader.unload_plugin()
                         v
                    ┌─────────┐
                    │ UNLOADED│ ←── publish PluginUnloaded
                    └────┬────┘
                         │ registry.remove()
                         v
                    ┌─────────┐
                    │ REMOVED │ ←── publish PluginRemoved
                    └─────────┘

Any state → FAILED (on error) ←── publish PluginFailed
```

## Plugin Manifest Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `str` | Yes | Unique plugin identifier |
| `name` | `str` | Yes | Human-readable name |
| `version` | `str` (X.Y.Z) | Yes | Semantic version |
| `author` | `str` | No | Developer/org name |
| `description` | `str` | No | What the plugin does |
| `dependencies` | `list` | No | Required/optional plugin dependencies |
| `required_capabilities` | `list[str]` | No | Capability IDs needed |
| `permissions` | `list` | No | Permission declarations |
| `min_friday_version` | `str` | No | Minimum FRIDAY version requirement |
| `entry_point` | `str` | No | Module entry point |
| `metadata` | `dict` | No | Extensible metadata |

## Dependency Resolution

```
Plugin A depends on Plugin B (required).
Plugin B depends on Plugin C (required).

Loading A:
  1. Check B is registered + enabled → if not, A fails
  2. B's dep on C is already resolved when B was loaded
  3. If B is loaded but C is missing, B would have already failed
```

## Health Model

```
PluginHealth per plugin:
  ├─ status: "unknown" | "installed" | "failed"
  ├─ enabled: bool
  ├─ loaded: bool
  ├─ load_time_ms: float
  ├─ crash_count: int
  ├─ last_error: Optional[str]
  ├─ last_loaded: Optional[datetime]
  └─ last_enabled: Optional[datetime]

PluginEngineHealth (aggregate):
  ├─ total_plugins
  ├─ enabled_plugins
  ├─ loaded_plugins
  ├─ failed_plugins
  ├─ disabled_plugins
  └─ total_crashes
```

## Performance

| Operation | Complexity | Notes |
|---|---|---|
| `install` | O(1) | Dict insert |
| `get` | O(1) | Dict lookup |
| `remove` | O(1) | Dict pop |
| `update_state` | O(1) | Dict lookup + field update |
| `search` | O(n) | Linear string match |
| `list_by_state` | O(n) | Linear filter |
| `get_dependency_graph` | O(n) | Build adjacency list |
| `aggregate_health` | O(n) | Summation pass |
| `load_from_directory` | O(d) | d = directory entries |

## Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| `PluginRegistry` | `EventBus` (optional) | Event publishing |
| `PluginLoader` | `PluginRegistry` | Plugin installation |
| `PluginLoader` | `PermissionValidator` | Permission checks |
| `PluginLoader` | `EventBus` (optional) | Event publishing |
