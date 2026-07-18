from __future__ import annotations

import os
from typing import Dict, List, Optional, Set
from loguru import logger

from app.workspace.models import (
    FileNode, ModuleNode, ImportEdge, ProjectGraph, Technology,
)


class GraphBuilder:
    """Builds and analyses project graphs.

    Supports incremental updates: given a previously built graph and a set
    of changed files, only re-process those files and their dependents.
    """

    def __init__(self, project_root: str, project_name: str = "") -> None:
        self._root = os.path.abspath(project_root)
        self._name = project_name or os.path.basename(self._root)

    def build(
        self,
        files: Dict[str, FileNode],
        technologies: Optional[Set[Technology]] = None,
    ) -> ProjectGraph:
        graph = ProjectGraph(
            root=self._root,
            name=self._name,
            technologies=technologies or set(),
        )

        for fpath, node in files.items():
            graph.add_file(node)

        self._compute_imports(graph)
        self._detect_modules(graph)
        self._detect_entry_points(graph)

        logger.info(
            f"Graph built for '{self._name}': "
            f"{graph.stats().total_files} files, "
            f"{len(graph.modules)} modules, "
            f"{len(graph.imports)} imports"
        )

        return graph

    def incremental_update(
        self,
        graph: ProjectGraph,
        changed_files: Dict[str, FileNode],
        deleted_files: Optional[List[str]] = None,
    ) -> ProjectGraph:
        """Update an existing graph with only the changed files.

        Removes deleted files and their import edges, adds/updates changed
        files, re-computes imports for changed files and any files that
        imported them.
        """
        deleted = deleted_files or []

        for fpath in deleted:
            norm = os.path.normpath(fpath)
            graph.files.pop(norm, None)
            graph.imports = [
                e for e in graph.imports
                if os.path.normpath(e.source) != norm
            ]
            self._remove_from_modules(graph, norm)

        for fpath, node in changed_files.items():
            norm = os.path.normpath(fpath)
            old_node = graph.files.get(norm)

            old_imports: Set[str] = set()
            if old_node:
                old_imports = set(old_node.imports)

            graph.add_file(node)

            graph.imports = [
                e for e in graph.imports
                if os.path.normpath(e.source) != norm
            ]

            self._update_module_membership(graph, node)

        for fpath, node in changed_files.items():
            norm = os.path.normpath(fpath)
            ext = os.path.splitext(norm)[1].lower()
            imports = self._extract_imports(norm, ext)
            node.imports = imports
            for imp in imports:
                graph.imports.append(ImportEdge(source=norm, target=imp))

        self._detect_entry_points(graph)

        return graph

    def _compute_imports(self, graph: ProjectGraph) -> None:
        for fpath, node in graph.files.items():
            ext = os.path.splitext(fpath)[1].lower()
            imports = self._extract_imports(fpath, ext)
            node.imports = imports
            for imp in imports:
                graph.imports.append(ImportEdge(source=fpath, target=imp))

    def _extract_imports(self, file_path: str, ext: str) -> List[str]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            return []

        if ext == ".py":
            return self._parse_python_imports(content)
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            return self._parse_js_imports(content)
        return []

    def _parse_python_imports(self, content: str) -> List[str]:
        imports: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                parts = stripped.split()
                if len(parts) >= 2:
                    imports.append(parts[1])
            elif stripped.startswith("from "):
                parts = stripped.split()
                if len(parts) >= 2:
                    imports.append(parts[1])
        return imports

    def _parse_js_imports(self, content: str) -> List[str]:
        imports: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("const "):
                if "from " in stripped:
                    idx = stripped.index("from ")
                    rest = stripped[idx + 5:].strip().strip("\"'`;")
                    if rest:
                        imports.append(rest)
        return imports

    def _detect_modules(self, graph: ProjectGraph) -> None:
        for fpath in list(graph.files.keys()):
            parent = os.path.dirname(fpath)
            if parent == graph.root:
                continue
            rel = os.path.relpath(parent, graph.root)
            parts = rel.replace(os.sep, "/").split("/")
            module_name = parts[0] if parts else rel
            if module_name not in graph.modules:
                root_mod = os.path.join(graph.root, module_name)
                graph.modules[module_name] = ModuleNode(
                    name=module_name,
                    root_path=root_mod,
                    is_package=os.path.isdir(root_mod),
                )
            graph.modules[module_name].files.append(fpath)

    def _detect_entry_points(self, graph: ProjectGraph) -> None:
        graph.entry_points.clear()
        for fpath, node in graph.files.items():
            name = node.name.lower()
            if name in (
                "main.py", "index.ts", "index.js", "app.py",
                "cli.py", "server.py", "__main__.py",
                "main.go", "main.rs", "main.java",
                "app.ts", "app.js", "server.ts", "server.js",
            ):
                node.is_entry_point = True
                graph.entry_points.append(fpath)

    def _remove_from_modules(self, graph: ProjectGraph, norm: str) -> None:
        to_delete: List[str] = []
        for mname, mod in graph.modules.items():
            if norm in mod.files:
                mod.files.remove(norm)
            if not mod.files:
                to_delete.append(mname)
        for mname in to_delete:
            del graph.modules[mname]

    def _update_module_membership(
        self,
        graph: ProjectGraph,
        node: FileNode,
    ) -> None:
        parent = os.path.dirname(node.path)
        if parent == graph.root:
            return
        try:
            rel = os.path.relpath(parent, graph.root)
        except ValueError:
            return
        parts = rel.replace(os.sep, "/").split("/")
        module_name = parts[0] if parts else rel
        if module_name not in graph.modules:
            root_mod = os.path.join(graph.root, module_name)
            graph.modules[module_name] = ModuleNode(
                name=module_name,
                root_path=root_mod,
                is_package=os.path.isdir(root_mod),
            )
        if node.path not in graph.modules[module_name].files:
            graph.modules[module_name].files.append(node.path)
