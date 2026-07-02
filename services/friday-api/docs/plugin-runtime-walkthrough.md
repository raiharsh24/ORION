# Plugin Runtime Walkthrough

## Overview

The Plugin Runtime extends the Plugin SDK with sandboxed execution, hot
reload, resource monitoring, and full lifecycle management.

Plugin Runtime builds on top of the Plugin SDK. Plugins are discovered from
local directories, validated, loaded into the SDK registry, sandboxed during
execution, and hot-reloadable when files change.

## Quick Start

```python
from app.plugins.registry import PluginRegistry as SdkPluginRegistry
from app.plugin_runtime.runtime import PluginRuntime
from app.plugin_runtime.base import PluginRuntimeConfig

sdk_registry = SdkPluginRegistry(event_bus=event_bus)
config = PluginRuntimeConfig(
    plugin_dirs=["./plugins"],
    watch_enabled=True,
    auto_load=True,
)

runtime = PluginRuntime(
    sdk_registry=sdk_registry,
    event_bus=event_bus,
    config=config,
)

await runtime.start()
# Discovers, loads, and initializes all plugins in ./plugins

# Execute a plugin function
result = await runtime.execute("my_plugin", my_plugin.do_something())

# Suspend/resume
await runtime.suspend_plugin("my_plugin", "maintenance")
await runtime.resume_plugin("my_plugin")

# Hot reload
await runtime.reload_plugin("my_plugin")

# Check health
health = runtime.health()
print(health.overall_status, health.running_plugins)

await runtime.shutdown()
```

## Plugin Lifecycle

```
DISCOVERED → VALIDATED → LOADING → LOADED → INITIALIZING → INITIALIZED
                                                                    │
                                                                    ↓
                                                               REGISTERING
                                                                    │
                                                                    ↓
                                           ┌─────────────────── READY
                                           │                     │
                                           │              ┌──────┴──────┐
                                           │              │             │
                                      SUSPENDED       EXECUTING     RELOADING
                                           │              │             │
                                           └──── RESUME ──┘     ┌──────┘
                                           │                     │
                                           └──── RELOAD ─────────┘
                                                                    │
                                                               UNLOADING
                                                                    │
                                                               UNLOADED
                                                                    │
                                                               CLEANING
```

## Loading Plugins

```python
# Discover from directory
runtime.loader.discover("./plugins")
# Returns list of plugin IDs discovered

# Load a discovered plugin
inst = await runtime.load_plugin("my_plugin")
# Returns PluginInstance in READY state

# Load from directory in one step
result = runtime.loader.load_from_directory("./plugins")
print(result["discovered"])  # ["plugin_a", "plugin_b"]
```

## Sandbox Execution

```python
# Execute an async function with sandbox
async def my_func():
    return 42

result = await runtime.execute("my_plugin", my_func())

# Sandbox enforces:
# - Execution timeout (default: 30s)
# - Filesystem permissions
# - Network permissions
# - Import restrictions
# - Subprocess restrictions
```

## Permission Enforcement

```python
# Check permissions at runtime
enforcer = runtime.permission_enforcer
enforcer.grant("my_plugin", "filesystem.read")

if enforcer.check_filesystem_access("my_plugin", "MyPlugin", "/tmp/test"):
    # Access allowed
    pass

# View violations
violations = enforcer.get_violations("my_plugin")
```

## Hot Reload

```python
# Enable directory watching
await runtime.reloader.start_watching("./plugins")
# Automatically detects file changes and reloads

# Manual reload
await runtime.reload_plugin("my_plugin")

# Register reload callbacks
async def on_reload(plugin_id):
    print(f"Plugin {plugin_id} was reloaded")

runtime.reloader.on_reload(on_reload)

# Stop watching
await runtime.reloader.stop_watching()
```

## Health Monitoring

```python
health = runtime.health()
print(health.overall_status)     # "healthy" | "degraded" | "critical"
print(health.total_plugins)      # Total registered
print(health.running_plugins)    # In READY state
print(health.failed_plugins)     # In FAILED state
print(health.sandbox_violations) # Total violations
print(health.total_executions)   # Total execution count
print(health.last_crash)         # Most recent crash record
```
