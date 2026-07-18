from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set
from loguru import logger

from app.workspace.models import ProjectRoot, ProjectGraph, Technology
from app.workspace.scanner import WorkspaceScanner
from app.workspace.watcher import (
    WorkspaceWatcher, WorkspaceChangeEvent, ChangeType,
)


class WorkspaceContextProvider:
    """Bridges workspace intelligence to the planner and runtime.

    Owns the WorkspaceScanner, caches ProjectRoot/ProjectGraph objects,
    and exposes context for the planner's CapabilityResolver.
    """

    def __init__(
        self,
        scanner: Optional[WorkspaceScanner] = None,
        watcher: Optional[WorkspaceWatcher] = None,
    ) -> None:
        self._scanner = scanner or WorkspaceScanner()
        self._watcher = watcher
        self._projects: Dict[str, ProjectRoot] = {}
        self._graphs: Dict[str, ProjectGraph] = {}
        self._last_scan_time: float = 0.0

    # ── Project Discovery ──────────────────────────────────────────────

    async def discover_projects(
        self,
        scan_path: Optional[str] = None,
        rescan: bool = False,
    ) -> List[ProjectRoot]:
        """Discover project roots. Caches results unless rescan=True."""
        if self._projects and not rescan:
            return list(self._projects.values())

        roots = self._scanner.discover_roots(scan_path)
        self._projects = {r.path: r for r in roots}

        for r in roots:
            if self._watcher:
                self._watcher.watch(r.path)

        import time
        self._last_scan_time = time.time()

        logger.info(f"Discovered {len(roots)} project(s)")
        return roots

    def get_projects(self) -> List[ProjectRoot]:
        return list(self._projects.values())

    def get_project(self, path: str) -> Optional[ProjectRoot]:
        norm = os.path.normpath(path)
        return self._projects.get(norm)

    # ── Graph Building ─────────────────────────────────────────────────

    async def build_graph(
        self,
        project_path: str,
        compute_imports: bool = True,
        force: bool = False,
    ) -> Optional[ProjectGraph]:
        """Build or retrieve cached ProjectGraph for a project."""
        norm = os.path.normpath(project_path)

        if norm in self._graphs and not force:
            return self._graphs[norm]

        project = self.get_project(norm)
        if not project:
            project = self._scanner._build_project_root(norm)
            self._projects[norm] = project

        graph = self._scanner.scan_project(
            project, compute_imports=compute_imports,
        )
        self._graphs[norm] = graph
        return graph

    def get_graph(self, project_path: str) -> Optional[ProjectGraph]:
        norm = os.path.normpath(project_path)
        return self._graphs.get(norm)

    def get_graphs(self) -> Dict[str, ProjectGraph]:
        return dict(self._graphs)

    # ── Incremental Update ─────────────────────────────────────────────

    def handle_change(self, event: WorkspaceChangeEvent) -> None:
        """Process a file change event and update the relevant graph."""
        project = self._resolve_project(event.file_path)
        if not project:
            return

        norm = os.path.normpath(project.path)
        graph = self._graphs.get(norm)
        if not graph:
            return

        self._scanner.scan_project(project, compute_imports=True)

    def _resolve_project(self, file_path: str) -> Optional[ProjectRoot]:
        norm = os.path.normpath(file_path)
        for proj in self._projects.values():
            if norm.startswith(os.path.normpath(proj.path) + os.sep) or norm == os.path.normpath(proj.path):
                return proj
        return None

    # ── Context for Planner ────────────────────────────────────────────

    def get_workspace_context(self) -> Dict[str, Any]:
        """Return a summary of workspace state for planner context injection."""
        projects_info = []
        for proj in self._projects.values():
            graph = self._graphs.get(os.path.normpath(proj.path))
            stats = graph.stats() if graph else None
            projects_info.append({
                "name": proj.name,
                "path": proj.path,
                "technologies": [t.value for t in proj.technologies],
                "is_git": proj.is_git,
                "branch": proj.branch,
                "file_count": proj.file_count,
                "graph_stats": {
                    "total_files": stats.total_files if stats else 0,
                    "total_modules": stats.total_modules if stats else 0,
                    "total_imports": stats.total_imports if stats else 0,
                    "entry_points": stats.entry_points if stats else 0,
                    "files_by_extension": stats.files_by_extension if stats else {},
                } if stats else None,
            })

        return {
            "workspace_root": self._scanner.root_dir,
            "projects": projects_info,
            "project_count": len(self._projects),
        }

    def get_project_context(self, project_path: str) -> Dict[str, Any]:
        """Return detailed context for a specific project."""
        graph = self.get_graph(project_path)
        if not graph:
            return {"error": "Project not indexed"}

        stats = graph.stats()
        modules_list = [
            {
                "name": m.name,
                "file_count": len(m.files),
                "is_package": m.is_package,
            }
            for m in graph.modules.values()
        ]
        entry_points = [
            os.path.relpath(ep, graph.root)
            for ep in graph.entry_points
        ]

        return {
            "name": graph.name,
            "root": graph.root,
            "technologies": [t.value for t in graph.technologies],
            "stats": {
                "total_files": stats.total_files,
                "total_modules": stats.total_modules,
                "total_imports": stats.total_imports,
                "entry_points": stats.entry_points,
                "files_by_extension": stats.files_by_extension,
            },
            "modules": modules_list,
            "entry_points": entry_points,
        }

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start_watcher(self) -> None:
        if self._watcher:
            self._watcher.on_change(self.handle_change)
            await self._watcher.start()

    async def stop_watcher(self) -> None:
        if self._watcher:
            self._watcher.remove_handler(self.handle_change)
            await self._watcher.stop()

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "projects_cached": len(self._projects),
            "graphs_cached": len(self._graphs),
            "watcher_running": self._watcher is not None,
        }


class WorkspaceAwareCapabilityResolver:
    """Extends the planner's capability resolution with workspace awareness.

    Injects workspace-related capabilities when the planner detects
    workspace-relevant intents (e.g., project analysis, code search).
    """

    WORKSPACE_CAPABILITIES = [
        "Workspace",
        "WorkspaceAnalysis",
        "CodeSearch",
        "ProjectGraph",
        "FileInspection",
    ]

    WORKSPACE_INTENTS = {
        "Filesystem Action",
        "Project Management",
        "Tool Invocation",
    }

    def resolve(
        self,
        intent: str,
        base_capabilities: List[str],
    ) -> List[str]:
        resolved = list(base_capabilities)

        if intent in self.WORKSPACE_INTENTS:
            resolved.extend(self.WORKSPACE_CAPABILITIES)

        return list(set(resolved))


class KnowledgeIntegration:
    """Bridges workspace scanning with the Knowledge Engine indexer.

    When a project is scanned, discovered files can be automatically
    indexed into the Knowledge Engine for semantic retrieval.
    """

    def __init__(self, knowledge_manager: Any) -> None:
        self._km = knowledge_manager
        self._indexed_count = 0

    async def index_project_files(
        self,
        graph: ProjectGraph,
        extensions: Optional[Set[str]] = None,
    ) -> int:
        """Index all files in a project graph into the Knowledge Engine."""
        allowed = extensions or {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt",
            ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
            ".rst", ".html", ".css", ".scss",
        }

        count = 0
        for fpath, node in graph.files.items():
            ext = os.path.splitext(fpath)[1].lower()
            if ext not in allowed:
                continue
            if node.extension == "(no ext)":
                continue

            try:
                await self._km.index_file(fpath, chunk_size=500)
                count += 1
            except Exception as e:
                logger.debug(
                    f"Skipping index for {fpath}: {e}"
                )

        self._indexed_count += count
        logger.info(f"Indexed {count} files into Knowledge Engine")
        return count

    async def index_file(self, file_path: str) -> bool:
        """Index a single file."""
        try:
            await self._km.index_file(file_path, chunk_size=500)
            self._indexed_count += 1
            return True
        except Exception as e:
            logger.warning(f"Failed to index {file_path}: {e}")
            return False

    async def remove_file(self, file_path: str) -> bool:
        """Remove a file from the Knowledge Engine index."""
        try:
            await self._km.delete_document(file_path)
            self._indexed_count = max(0, self._indexed_count - 1)
            return True
        except Exception as e:
            logger.warning(f"Failed to remove {file_path}: {e}")
            return False

    @property
    def indexed_count(self) -> int:
        return self._indexed_count
