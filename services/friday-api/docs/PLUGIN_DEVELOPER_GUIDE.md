# Plugin Developer Guide

## Overview

FRIDAY plugins are Python modules that extend FRIDAY's capabilities. Each plugin is a directory containing a manifest (`plugin.json`) and an entry point (`main.py`) that exports a `BasePlugin` subclass.

## Writing a Plugin

### 1. Create the directory structure

```
plugins/my_plugin/
├── plugin.json
└── main.py
```

### 2. Write the manifest

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "You",
  "description": "Does something useful",
  "entry_point": "main",
  "permissions": [
    {"id": "filesystem.read", "description": "Read files"}
  ]
}
```

### 3. Write the plugin class

```python
from app.plugin_sdk.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    id = "my_plugin"
    name = "My Plugin"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("MyPlugin loaded")

    async def on_enable(self) -> None:
        self.log_info("MyPlugin enabled")

    async def on_disable(self) -> None:
        self.log_info("MyPlugin disabled")

    async def on_unload(self) -> None:
        self.log_info("MyPlugin unloaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["filesystem.read"]

    def do_something(self) -> str:
        return "Hello from MyPlugin"
```

## Lifecycle

| Stage | Hook | When |
|---|---|---|
| Installation | `on_install()` | Plugin first registered |
| Loading | `on_load()` | Module imported + instantiated |
| Initialization | `on_init()` | After dependency validation |
| Enable | `on_enable()` | Plugin marked ready |
| Disable | `on_disable()` | Before unload |
| Unload | `on_unload()` | Plugin being removed |
| Config change | `on_config_change(config)` | Configuration updated |

## PluginContext

Each plugin instance has a `self.context` (type `PluginContext`) providing access to FRIDAY services:

| Method | Description |
|---|---|
| `log_debug(msg)` | Log at DEBUG level |
| `log_info(msg)` | Log at INFO level |
| `log_warning(msg)` | Log at WARNING level |
| `log_error(msg)` | Log at ERROR level |
| `get_setting(key, default)` | Read a setting |
| `update_setting(key, value)` | Write a setting |
| `publish_event(topic, data)` | Publish an event |
| `register_tool(tool_id, instance)` | Register a tool in the tool registry |
| `unregister_tool(tool_id)` | Remove a tool from the registry |
| `query_memory(query, limit)` | Search FRIDAY memory |
| `create_plan(prompt)` | Create an execution plan |
| `retrieve_context(query, top_k)` | Get cognitive context (semantic + graph) |

## Example: Calculator Plugin

```python
from app.plugin_sdk.base_plugin import BasePlugin

class CalculatorPlugin(BasePlugin):
    id = "calculator"
    name = "Calculator"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Calculator loaded")

    def get_manifest(self):
        return {"id": self.id, "name": self.name, "version": self.version}

    def add(self, a: float, b: float) -> float:
        return a + b
```

## Testing

Create a test file and use `BasePlugin` directly:

```python
import pytest
from plugins.my_plugin.main import MyPlugin

@pytest.mark.asyncio
async def test_my_plugin():
    plugin = MyPlugin()
    assert plugin.do_something() == "Hello from MyPlugin"
```
