# Plugin SDK Walkthrough

## Overview

The Plugin SDK enables external developers to build FRIDAY extensions using a
stable API. It supports local plugins with manifest validation, dependency
resolution, permission management, and full lifecycle control.

**No marketplace, no cloud agents, no remote downloading.** Local plugins only.

## Architecture

```
PluginLoader
  ├─ loads from local directory
  ├─ validates manifest
  ├─ checks permissions
  ├─ resolves dependencies
  └─ PluginRegistry.install()
       │
PluginRegistry
  ├─ CRUD: install, get, remove, search
  ├─ lifecycle: update_state (loaded/enabled/disabled/unloaded/failed)
  ├─ health tracking per plugin
  ├─ dependency graph
  ├─ aggregate health
  └─ events
       │
PermissionValidator
  ├─ grant/revoke permissions
  ├─ validate pre-install
  └─ validate post-install
```

## Plugin Lifecycle

```
INSTALLED → LOADED → INITIALIZED → ENABLED
                                      ↓
                                   DISABLED
                                      ↓
                                   UNLOADED
                                      ↓
                                   REMOVED

Any state → FAILED (on error)
```

## Plugin Manifest (plugin.json)

Place a `plugin.json` or `manifest.json` in a subdirectory under the plugins
directory:

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "Developer Name",
  "description": "Does something useful",
  "dependencies": [
    {"id": "base_utils", "version": ">=1.0.0", "optional": false}
  ],
  "permissions": [
    {"id": "filesystem.read", "description": "Read files"}
  ],
  "required_capabilities": ["file_analysis"],
  "min_friday_version": "1.0.0",
  "entry_point": "",
  "metadata": {}
}
```

## Quick Start

```python
from app.plugins.registry import PluginRegistry
from app.plugins.loader import PluginLoader
from app.plugins.permissions import PermissionValidator

# Setup
pv = PermissionValidator()
pv.grant("filesystem.read")

registry = PluginRegistry(event_bus=event_bus)
loader = PluginLoader(registry, pv, event_bus=event_bus)

# Load all plugins from a directory
results = loader.load_from_directory("/path/to/plugins")
print(results["loaded"])   # ["my_plugin", ...]
print(results["failed"])   # []

# Enable a plugin
loader.enable_plugin("my_plugin")

# Check plugin state
plugin = registry.get("my_plugin")
print(plugin.state)         # PluginState.ENABLED
print(plugin.is_enabled)    # True
```

## Loading Plugins

```python
# Load a single plugin from a manifest
from app.plugins.base import PluginManifest, PluginDependency, PluginPermission
from app.plugins.manifest import parse_manifest, validate_manifest

manifest = parse_manifest(Path("./my_plugin/plugin.json"))
errors = validate_manifest(manifest)
if not errors:
    plugin = loader.load_plugin(manifest)
```

## Lifecycle Management

```python
# Enable a loaded plugin
loader.enable_plugin("my_plugin")

# Disable
loader.disable_plugin("my_plugin")

# Unload
loader.unload_plugin("my_plugin")

# Remove from registry
registry.remove("my_plugin")

# Check state
plugin = registry.get("my_plugin")
print(plugin.state.value)  # "installed", "loaded", "enabled", etc.
```

## Permission Model

```python
from app.plugins.permissions import PermissionValidator

pv = PermissionValidator()

# Grant permissions that plugins may request
pv.grant("filesystem.read")
pv.grant("network")

# Check if granted
pv.is_granted("network")  # True

# Revoke
pv.revoke("network")

# Validate before loading (blocks install if missing)
errors = pv.validate_pre_install(plugin.permissions)
```

## Dependency Resolution

Dependencies are resolved during loading:

- **Required dependencies** — the dependency must be loaded and enabled,
  or loading fails
- **Optional dependencies** — missing optional deps are logged as warnings

```python
manifest = PluginManifest(
    id="advanced",
    name="Advanced Plugin",
    version="1.0.0",
    dependencies=[
        PluginDependency(plugin_id="base_utils", optional=False),
        PluginDependency(plugin_id="optional_helper", optional=True),
    ],
)
# base_utils must be loaded first or loading fails
```

## Search & Discovery

```python
# Search by id, name, or description
results = registry.search("plugin")

# List all plugins
all_plugins = registry.list_plugins()

# List metadata (lighter weight)
metas = registry.list_metadata()

# Filter by state
enabled = registry.list_by_state(PluginState.ENABLED)
```

## Events

| Event | Trigger |
|---|---|
| `PluginInstalled` | plugin registered |
| `PluginLoaded` | plugin loaded |
| `PluginEnabled` | plugin enabled |
| `PluginDisabled` | plugin disabled |
| `PluginUnloaded` | plugin unloaded |
| `PluginRemoved` | plugin removed |
| `PluginFailed` | plugin entered FAILED state |

## Health

```python
# Per-plugin health
health = registry.get_health("my_plugin")
print(health.enabled)       # True
print(health.loaded)        # True
print(health.crash_count)   # 0
print(health.last_error)    # None

# Aggregate engine health
engine_health = registry.aggregate_health()
print(engine_health.total_plugins)
print(engine_health.enabled_plugins)
print(engine_health.failed_plugins)
```
