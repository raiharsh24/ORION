# Plugin Runtime Audit — Milestone 3, Phase 1

## Existing Code Layers

### Layer 1: `app/plugins/` (Phase 7 SDK — Data Models)
| Component | Status | Notes |
|---|---|---|
| `base.py` | ✅ Complete | `Plugin`, `PluginState`, `PluginVersion`, `PluginManifest`, `PluginDependency`, `PluginPermission`, `PluginHealth` |
| `manifest.py` | ⚠️ Partial | Missing `configuration_schema` field |
| `registry.py` | ✅ Complete | `PluginRegistry` with CRUD, dependency graph, health aggregation |
| `loader.py` | ⚠️ Partial | Loads manifests but never imports plugin Python code |
| `permissions.py` | ⚠️ Partial | `PermissionValidator` grants upfront, no prompt flow |
| `plugin.py` | ❌ Stub | `PluginWrapper` has empty hooks |
| `events.py` | ✅ Complete | Lifecycle event types |
| `health.py` | ✅ Complete | `PluginEngineHealth` dataclass |

### Layer 2: `app/plugin_runtime/` (Phase 7 Sprint 2 — Runtime)
| Component | Status | Notes |
|---|---|---|
| `runtime.py` | ✅ Complete | Top-level orchestrator |
| `loader.py` | ⚠️ Partial | `RuntimePluginLoader` discovers manifests but never imports/instantiates plugin Python classes |
| `unloader.py` | ✅ Complete | Cleanup + state transition |
| `reloader.py` | ✅ Complete | File watcher + reload |
| `sandbox.py` | ✅ Complete | Timeout + permission checks |
| `permissions.py` | ✅ Complete | `PermissionEnforcer` with fs/network/import checks |
| `security.py` | ✅ Complete | `SecurityConfig`, `FileSystemRule`, `NetworkRule`, `SecurityPolicy` |
| `monitor.py` | ✅ Complete | Execution stats, crash history |
| `registry.py` | ✅ Complete | Query runtime instances |
| `base.py` | ✅ Complete | `PluginInstance`, `PluginRuntimeState`, `PluginRuntimeConfig` |
| `events.py` | ✅ Complete | Runtime events |

### Layer 3: `app/plugin_security/` (Phase 7 Sprint 4)
- ✅ Signature/trust/certificate infrastructure — future-ready, works for local

### Layer 4: `app/kernel/plugin_api.py`
- ❌ `FridayPlugin` ABC exists but is never actually used by the runtime

## Critical Gaps

1. **No plugin Python code is ever executed.** The `RuntimePluginLoader` discovers manifests, validates, tracks state — but never calls `importlib.import_module()` to load a plugin's Python module.
2. **No BasePlugin class.** Plugin authors have no base class to extend. `FridayPlugin` is an ABC with no convenience methods. `PluginWrapper` has empty method stubs.
3. **No PluginContext.** Plugins cannot access FRIDAY services (tools, memory, planner, events).
4. **No tool registration from plugins.** No mechanism for a plugin to expose tools to the tool registry.
5. **No example plugins.** Zero plugins exist to validate the system.
6. **No permission prompt flow.** Permissions are granted upfront; plugins can't request at runtime.
7. **Configuration schema not in manifest.** The `PluginManifest` has no `configuration_schema` field.
8. **Terminal/browser/memory permission types not defined.** Only filesystem and network are granular.

## Reuse Strategy

- Keep all existing `app/plugins/` and `app/plugin_runtime/` code
- Create `app/plugin_sdk/` for the developer-facing SDK (BasePlugin + PluginContext)
- Modify `RuntimePluginLoader` to import modules + call lifecycle hooks
- Add `configuration_schema` to `PluginManifest`
- Add permission types + prompt mechanism
- Create example plugins under `plugins/`
- No changes to `app/plugin_marketplace/` (out of scope)
