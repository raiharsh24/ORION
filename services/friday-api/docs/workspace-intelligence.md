# Workspace Intelligence — Phase 9

## Overview

Workspace Intelligence gives ORION awareness of its project surroundings: it
discovers project roots, detects technologies, builds dependency graphs,
watches for file changes, and integrates with the Planner and Knowledge
Engine.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WorkspaceContextProvider                  │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ WorkspaceScanner │  │ GraphBuilder │  │ WorkspaceWatcher│ │
│  └────────┬────────┘  └──────┬───────┘  └───────┬───────┘  │
│           │                  │                   │          │
│           ▼                  ▼                   ▼          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ProjectGraph / ProjectRoot cache                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                    │                                        │
└────────────────────┼────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
   Knowledge     Planner      Runtime
    Engine     (Capability    (Middleware
               Resolver)      Context)
```

## Components

### `app/workspace/models.py`
- `FileNode`, `ModuleNode`, `ImportEdge` — core graph primitives.
- `ProjectRoot` — discovered project metadata (path, technologies, git info).
- `ProjectGraph` — a complete dependency graph of a project.
- `GraphStats` — aggregated statistics (file counts, modules, imports).
- `Technology` — enum of detected technologies (Python, JS, TS, Go, Rust, etc.).

### `app/workspace/scanner.py` — `WorkspaceScanner`
- `discover_roots(path)` — walks the filesystem looking for indicator files
  (`.git`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`).
- `detect_technologies(root)` — scans for file extensions and config files to
  infer which technologies a project uses.
- `scan_project(project)` — builds a `ProjectGraph` from a `ProjectRoot`:
  walks files, computes hashes for change detection, extracts imports,
  discovers module structure and entry points.
- Ignores `.git`, `node_modules`, `.venv`, `__pycache__`, etc.

### `app/workspace/graph.py` — `GraphBuilder`
- `build(files)` — construct a `ProjectGraph` from scanned file nodes.
- `incremental_update(graph, changed, deleted)` — efficient re-processing of
  only changed/deleted files and their dependents.
- Handles Python (`import`/`from`) and JS/TS (`import ... from`) imports.

### `app/workspace/watcher.py` — `WorkspaceWatcher`
- Polling-based file watcher (no third-party dependencies).
- Watched directories are scanned at a configurable `poll_interval`.
- `WorkspaceChangeEvent` emitted for `CREATED`, `MODIFIED`, `DELETED` files.
- Debounces rapid repeated events (last-write-wins).
- Ignores hidden files, `node_modules`, `.git`, and non-watched extensions.

### `app/workspace/integration.py`
- **`WorkspaceContextProvider`** — orchestrates scanner, graph builder, and
  watcher. Provides `get_workspace_context()` and `get_project_context()` for
  Planner and middleware consumption.
- **`WorkspaceAwareCapabilityResolver`** — injects workspace-related
  capabilities (`Workspace`, `CodeSearch`, `ProjectGraph`, etc.) when the
  Planner detects relevant intents.
- **`KnowledgeIntegration`** — bridges scanning to the Knowledge Engine:
  `index_project_files(graph)` and `index_file(path)` push file content into
  the `KnowledgeManager` index for semantic retrieval.

## Data Flow

1. **Startup** — `WorkspaceContextProvider.discover_projects()` walks
   configured directories and caches `ProjectRoot` entries.
2. **Scan** — `WorkspaceScanner.scan_project()` produces a `ProjectGraph`
   with modules, imports, entry points, and technology labels.
3. **Graph Build** — `GraphBuilder.build()` computes the full dependency
   topology from scanned files.
4. **Watch** — `WorkspaceWatcher` polls for filesystem changes and emits
   events. `WorkspaceContextProvider.handle_change()` triggers incremental
   re-scans.
5. **Planner Integration** — `WorkspaceContextProvider.get_workspace_context()`
   is injected into Planner prompts. `WorkspaceAwareCapabilityResolver`
   activates workspace tools based on intent.
6. **Knowledge Indexing** — `KnowledgeIntegration.index_project_files()`
   pushes file contents into the Knowledge Engine for retrieval-augmented
   generation.

## Configuration

In `kernel/config.py`, `WorkspaceConfig`:
- `tracked_projects` — list of paths to monitor (default: workspace root).
- `watch_for_changes` — enable/disable file watcher.
- `poll_interval` — watcher polling frequency (default: 2.0 s).

## Usage

```python
from app.workspace import WorkspaceContextProvider

provider = WorkspaceContextProvider()

# Discover and scan projects
projects = await provider.discover_projects("/home/user/projects")
graph = await provider.build_graph(projects[0].path)

# Get context for the planner
workspace_ctx = provider.get_workspace_context()
project_ctx = provider.get_project_context(projects[0].path)
```

## Testing

Run the workspace intelligence test suite:
```bash
python -m pytest tests/test_workspace_intelligence.py -v
```
