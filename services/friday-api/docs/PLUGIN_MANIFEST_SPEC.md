# Plugin Manifest Specification

Each plugin is a directory containing a `plugin.json` (or `manifest.json`) manifest file and a `main.py` entry point.

## Example

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "Developer Name",
  "description": "What this plugin does",
  "entry_point": "main",
  "permissions": [
    {"id": "filesystem.read", "description": "Read files from disk"}
  ],
  "dependencies": [
    {"id": "base_utils", "version": ">=1.0.0", "optional": false}
  ],
  "min_friday_version": "1.0.0",
  "configuration_schema": {
    "type": "object",
    "properties": {
      "api_key": {"type": "string", "default": ""},
      "enabled": {"type": "boolean", "default": true}
    }
  }
}
```

## Fields

| Field | Required | Type | Description |
|---|---|---|---|
| `id` | Yes | string | Unique plugin identifier (lowercase, no spaces) |
| `name` | Yes | string | Human-readable plugin name |
| `version` | Yes | string | Semver X.Y.Z |
| `author` | No | string | Plugin author name |
| `description` | No | string | Short description |
| `entry_point` | No | string | Python module name without `.py` (default: `main`) |
| `permissions` | No | array | List of permission objects |
| `dependencies` | No | array | List of dependency objects |
| `required_capabilities` | No | array | List of capability strings |
| `min_friday_version` | No | string | Minimum FRIDAY version required |
| `configuration_schema` | No | object | JSON Schema for plugin configuration |

## Permission Object

```json
{"id": "filesystem.read", "description": "Read files from disk"}
```

## Dependency Object

```json
{"id": "base_utils", "version": ">=1.0.0", "optional": false}
```

## Supported Permission IDs

| ID | Description |
|---|---|
| `filesystem.read` | Read files from disk |
| `filesystem.write` | Write files to disk |
| `terminal.execute` | Execute terminal commands |
| `network` | Make network requests |
| `memory.read` | Read from FRIDAY memory |
| `memory.write` | Write to FRIDAY memory |
| `desktop.access` | Access desktop controller |
| `browser.control` | Control browser automation |
| `subprocess` | Spawn subprocesses |
| `native_code` | Load native code (ctypes/cffi) |
