# Plugin Runtime Architecture

## Design Principles

1. **Layer on SDK** — The Runtime uses the Plugin SDK for storage, manifest
   parsing, and basic lifecycle. The Runtime adds sandboxing, hot reload,
   monitoring, and execution.
2. **Defense in depth** — Security is enforced at import, filesystem, network,
   and subprocess levels. Permissions are checked before every operation.
3. **No process isolation** — Plugins run in-process within the FRIDAY kernel.
   Sandboxing is advisory (permission checks + timeouts + import restrictions).
4. **Hot reload without restart** — Plugin file changes are detected by a
   polling watcher. The plugin is unloaded, reloaded, and re-registered
   without restarting FRIDAY.
5. **Observable** — Every lifecycle transition publishes a FridayEvent.
   Health and monitoring provide execution statistics, crash history, and
   sandbox violation tracking.

## Package Structure

```
app/plugin_runtime/
├── __init__.py       # Public API exports
├── base.py           # Core models: PluginRuntimeState, PluginInstance,
│                     #   PluginRuntimeConfig, SandboxConfig, ResourceQuota,
│                     #   ExecutionStats
├── runtime.py        # PluginRuntime — top-level orchestrator
├── sandbox.py        # Sandbox — execution sandbox with permission enforcement
├── loader.py         # RuntimePluginLoader — discover, load, initialize
├── unloader.py       # PluginUnloader — safe unload with cleanup
├── reloader.py       # PluginReloader — hot reload with file watching
├── monitor.py        # PluginMonitor — execution tracking, crash recording
├── registry.py       # PluginRuntimeRegistry — query/search instances
├── health.py         # PluginRuntimeHealth model
├── events.py         # 12 FridayEvent subtypes
├── permissions.py    # PermissionEnforcer — grant/revoke/check
└── security.py       # Security models: SecurityPolicy, FileSystemRule,
                      #   NetworkRule, SecurityConfig
```

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        PluginRuntime                             │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Sandbox  │  │   Loader   │  │ Unloader │  │   Reloader   │  │
│  │          │  │            │  │          │  │              │  │
│  │• timeout │  │• discover  │  │• unload  │  │• watch dir   │  │
│  │• perms   │  │• validate  │  │• cleanup │  │• file detect │  │
│  │• imports │  │• load      │  │          │  │• reload      │  │
│  │• fs/net  │  │• initialize│  │          │  │              │  │
│  └────┬─────┘  └─────┬──────┘  └────┬─────┘  └──────┬───────┘  │
│       │              │              │               │          │
│       └──────────────┼──────────────┼───────────────┘          │
│                      │              │                          │
│              ┌───────▼──────────────▼───────────────┐           │
│              │          PluginMonitor               │           │
│              │  • execution stats  • crash history  │           │
│              │  • load times      • violations      │           │
│              └─────────────────────────────────────┘           │
│                                                                 │
│  Uses: SdkPluginRegistry, EventBus                              │
└─────────────────────────────────────────────────────────────────┘
```

## Core Data Flow

```
1. DISCOVERY
   PluginRuntime.start()
     ├─ loader.load_from_directory("./plugins")
     │    ├─ discover() → finds plugin.json → PluginManifest
     │    ├─ load() → sdk_registry.install(manifest)
     │    ├─ initialize()
     │    └─ mark_ready()
     └─ reloader.start_watching() (if watch_enabled)

2. EXECUTION
   runtime.execute(plugin_id, coro)
     ├─ sandbox.execute(plugin_id, name, coro, timeout)
     │    ├─ check permissions
     │    ├─ asyncio.wait_for(coro, timeout)
     │    └─ record execution in monitor
     └─ return result or raise error

3. HOT RELOAD
   reloader.reload(plugin_id)
     ├─ unloader.unload(inst)
     │    ├─ sdk_registry.remove()
     │    ├─ cleanup_permissions()
     │    └─ mark UNLOADED
     ├─ initialize() + mark_ready()
     ├─ increment reload_count
     └─ publish PluginReloaded

4. SUSPEND/RESUME
   runtime.suspend_plugin("my_plugin", "reason")
     └─ state → SUSPENDED
   runtime.resume_plugin("my_plugin")
     └─ state → READY
```

## Sandbox Enforcement Points

| Check | Method | Enforcement |
|---|---|---|
| Execution timeout | `sandbox.execute()` | `asyncio.wait_for()` |
| File read | `sandbox.check_filesystem_access(path, write=False)` | Permission check |
| File write | `sandbox.check_filesystem_access(path, write=True)` | Permission check |
| Network access | `sandbox.check_network_access(host, port)` | Permission check |
| Import | `sandbox.check_import(module_name)` | Permission check |
| Subprocess | `sandbox.check_subprocess_allowed()` | Permission check |

## Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| `PluginRuntime` | `SdkPluginRegistry`, `EventBus` | Orchestration |
| `RuntimePluginLoader` | `SdkPluginRegistry`, `Sandbox`, `Monitor` | Loading |
| `PluginUnloader` | `SdkPluginRegistry`, `Monitor` | Unloading |
| `PluginReloader` | `Loader`, `Unloader`, `Monitor` | Hot reload |
| `Sandbox` | `PermissionEnforcer`, `EventBus` | Execution |
| `PermissionEnforcer` | `SecurityConfig` | Permissions |
| `PluginMonitor` | (none) | Monitoring |
| `PluginRuntimeRegistry` | `Loader` | Query |
