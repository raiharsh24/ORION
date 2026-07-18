import pytest
import asyncio
import os
import tempfile
import time
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.workspace.models import (
    Technology, FileNode, ModuleNode, ImportEdge,
    ProjectRoot, ProjectGraph, GraphStats,
)
from app.workspace.scanner import WorkspaceScanner
from app.workspace.graph import GraphBuilder
from app.workspace.watcher import (
    WorkspaceWatcher, WorkspaceChangeEvent, ChangeType, WatchedDirectory,
)
from app.workspace.integration import (
    WorkspaceContextProvider,
    WorkspaceAwareCapabilityResolver,
    KnowledgeIntegration,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_files_dict(base: Path) -> dict:
    """Build a FileNode dict from actual files in a directory."""
    files: dict = {}
    for root, _dirs, fnames in os.walk(str(base)):
        for fname in fnames:
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower() or "(no ext)"
            stat = os.stat(fpath)
            files[fpath] = FileNode(
                path=fpath,
                name=fname,
                extension=ext,
                size=stat.st_size,
                mtime=stat.st_mtime,
                sha256="",
                language=None,
            )
    return files


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def temp_project():
    """Create a temporary project directory with sample files."""
    tmp = Path(tempfile.mkdtemp(prefix="orion_test_"))

    (tmp / "src").mkdir()
    (tmp / "src" / "__init__.py").write_text("")
    (tmp / "src" / "main.py").write_text(
        "import os\nimport sys\nfrom src import utils\n\n"
        "def run():\n    pass\n"
    )
    (tmp / "src" / "utils.py").write_text(
        "from src.models import User\n\ndef helper():\n    return 42\n"
    )
    (tmp / "src" / "models.py").write_text(
        "class User:\n    pass\n"
        "class Project:\n    pass\n"
    )

    (tmp / "web").mkdir()
    (tmp / "web" / "index.js").write_text(
        'import React from "react";\n'
        'import App from "./App";\n'
    )
    (tmp / "web" / "App.js").write_text(
        'import { Component } from "react";\n'
        'export default App;\n'
    )

    (tmp / "setup.cfg").write_text("[metadata]\nname = test\n")
    (tmp / "package.json").write_text('{"name": "test"}\n')

    (tmp / ".git").mkdir()
    (tmp / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

    yield tmp
    shutil.rmtree(str(tmp))


@pytest.fixture
def scanner():
    return WorkspaceScanner()


@pytest.fixture
def graph_builder(temp_project):
    return GraphBuilder(str(temp_project), project_name="test_project")


# ── WorkspaceScanner Tests ────────────────────────────────────────────────

class TestWorkspaceScanner:
    def test_discover_roots_finds_git_projects(self, temp_project, scanner):
        roots = scanner.discover_roots(str(temp_project))
        assert len(roots) >= 1
        found = [r for r in roots if r.path == str(temp_project)]
        assert len(found) == 1
        assert found[0].is_git is True
        assert found[0].branch is not None

    def test_discover_roots_with_exclusions(self, scanner):
        roots = scanner.discover_roots("/nonexistent")
        assert len(roots) == 0

    def test_scan_project_detects_technologies(self, temp_project, scanner):
        project = scanner._build_project_root(str(temp_project))
        graph = scanner.scan_project(project)
        techs = {t.value for t in graph.technologies}
        assert "python" in techs

    def test_scan_project_discovers_modules(self, temp_project, scanner):
        project = scanner._build_project_root(str(temp_project))
        graph = scanner.scan_project(project)
        assert len(graph.modules) >= 2

    def test_scan_project_finds_entry_points(self, temp_project, scanner):
        project = scanner._build_project_root(str(temp_project))
        graph = scanner.scan_project(project)
        entry_names = {os.path.basename(ep) for ep in graph.entry_points}
        assert "main.py" in entry_names or "index.js" in entry_names
        assert len(graph.entry_points) >= 1

    def test_scan_project_handles_empty_directory(self, scanner):
        with tempfile.TemporaryDirectory() as tmp:
            project = scanner._build_project_root(tmp)
            graph = scanner.scan_project(project)
            assert len(graph.files) == 0

    def test_detect_technologies_python(self, scanner):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "setup.py").write_text("from setuptools import setup\n")
            project = scanner._build_project_root(tmp)
            techs = {t.value for t in project.technologies}
            assert "python" in techs

    def test_detect_technologies_javascript(self, scanner):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "package.json").write_text('{"name": "test"}\n')
            project = scanner._build_project_root(tmp)
            techs = {t.value for t in project.technologies}
            assert "javascript" in techs

    def test_scan_respects_ignore_dirs(self, scanner):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "node_modules").mkdir()
            Path(tmp, "node_modules", "lib.py").write_text("# ignored")
            project = scanner._build_project_root(tmp)
            graph = scanner.scan_project(project)
            assert len(graph.files) == 0


# ── GraphBuilder Tests ────────────────────────────────────────────────────

class TestGraphBuilder:
    def test_build_creates_graph(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        assert graph.name == "test_project"
        assert graph.root == str(temp_project)
        assert len(graph.files) >= 1

    def test_build_detects_entry_points(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        assert len(graph.entry_points) >= 1
        ep_names = {os.path.basename(ep) for ep in graph.entry_points}
        assert "main.py" in ep_names or "index.js" in ep_names

    def test_import_extraction_python(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        imports_src = [
            e for e in graph.imports
            if os.path.basename(e.source) == "main.py"
        ]
        target_names = {os.path.basename(e.target) for e in imports_src}
        assert "os" in target_names or "sys" in target_names or "utils" in target_names

    def test_import_extraction_javascript(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        imports_js = [
            e for e in graph.imports
            if os.path.basename(e.source) == "App.js"
        ]
        target_names = {e.target for e in imports_js}
        assert any("react" in t.lower() for t in target_names)

    def test_incremental_update_adds_files(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        initial_count = len(graph.files)

        new_file = Path(temp_project, "src", "new_module.py")
        new_file.write_text("def new_func():\n    pass\n")

        new_files = _build_files_dict(temp_project)
        graph = graph_builder.incremental_update(graph, {
            str(new_file): new_files[str(new_file)]
        })

        assert len(graph.files) == initial_count + 1

    def test_incremental_update_removes_files(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        initial_count = len(graph.files)

        target = str(temp_project / "src" / "models.py")
        graph = graph_builder.incremental_update(
            graph, changed_files={}, deleted_files=[target]
        )

        assert len(graph.files) == initial_count - 1

    def test_graph_stats(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)
        stats = graph.stats()
        assert isinstance(stats, GraphStats)
        assert stats.total_files >= 1
        assert stats.total_imports >= 0
        assert stats.total_modules >= 0
        assert stats.entry_points >= 1

    def test_incremental_update_reprocesses_imports(self, temp_project, graph_builder):
        files = _build_files_dict(temp_project)
        graph = graph_builder.build(files)

        changed_file = Path(temp_project, "src", "main.py")
        changed_file.write_text(
            "import json\nimport math\nfrom src import new_module\n"
        )
        new_files = _build_files_dict(temp_project)
        graph = graph_builder.incremental_update(graph, {
            str(changed_file): new_files[str(changed_file)]
        })

        main_imports = [
            e for e in graph.imports
            if os.path.basename(e.source) == "main.py"
        ]
        target_names = {e.target for e in main_imports}
        assert "json" in target_names
        assert "math" in target_names


# ── Watcher Tests ─────────────────────────────────────────────────────────

class TestWorkspaceWatcher:
    def test_watch_directory_creates_entry(self):
        watcher = WorkspaceWatcher(poll_interval=0.1)
        watcher.watch("/tmp")
        assert "/tmp" in watcher._directories

    def test_unwatch_removes_entry(self):
        watcher = WorkspaceWatcher()
        watcher.watch("/tmp")
        watcher.unwatch("/tmp")
        assert "/tmp" not in watcher._directories

    def test_scan_detects_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)
            events = watcher.scan_now()
            assert len(events) == 0

            Path(tmp, "test.py").write_text("x = 1")
            events = watcher.scan_now()
            assert len(events) == 1
            assert events[0].change_type == ChangeType.CREATED
            assert events[0].file_path.endswith("test.py")

    def test_scan_detects_modified_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)

            Path(tmp, "test.py").write_text("x = 1")
            watcher.scan_now()

            time.sleep(0.02)
            Path(tmp, "test.py").write_text("x = 2")

            events = watcher.scan_now()
            assert len(events) == 1
            assert events[0].change_type == ChangeType.MODIFIED

    def test_scan_detects_deleted_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)

            fpath = Path(tmp, "test.py")
            fpath.write_text("x = 1")
            watcher.scan_now()

            fpath.unlink()
            events = watcher.scan_now()
            assert len(events) == 1
            assert events[0].change_type == ChangeType.DELETED

    def test_ignores_hidden_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)

            Path(tmp, ".hidden.py").write_text("x = 1")
            events = watcher.scan_now()
            assert len(events) == 0

    def test_ignores_ignore_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)

            Path(tmp, "node_modules").mkdir()
            Path(tmp, "node_modules", "lib.py").write_text("x = 1")
            events = watcher.scan_now()
            assert len(events) == 0

    def test_ignores_unwatched_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)

            Path(tmp, "data.bin").write_bytes(b"\x00\x01")
            events = watcher.scan_now()
            assert len(events) == 0

    def test_scan_now_returns_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = WorkspaceWatcher()
            watcher.watch(tmp)

            watcher.scan_now()
            Path(tmp, "test.py").write_text("x = 1")

            events = watcher.scan_now()
            assert len(events) == 1
            assert events[0].change_type == ChangeType.CREATED

    def test_remove_handler(self):
        watcher = WorkspaceWatcher()

        def handler(event):
            pass

        watcher.on_change(handler)
        watcher.remove_handler(handler)
        assert handler not in watcher._handlers


# ── Integration Tests ─────────────────────────────────────────────────────

class TestWorkspaceContextProvider:
    def test_provider_initialization(self):
        provider = WorkspaceContextProvider()
        assert provider.health()["status"] == "healthy"
        assert provider.health()["projects_cached"] == 0
        assert provider.health()["graphs_cached"] == 0

    def test_discover_projects(self, temp_project):
        provider = WorkspaceContextProvider()
        projects = asyncio.run(provider.discover_projects(str(temp_project)))
        assert len(projects) >= 1
        assert any(p.path == str(temp_project) for p in projects)

    def test_build_graph(self, temp_project):
        provider = WorkspaceContextProvider()
        asyncio.run(provider.discover_projects(str(temp_project)))
        graph = asyncio.run(provider.build_graph(str(temp_project)))
        assert graph is not None
        assert len(graph.files) >= 1

    def test_get_project_context(self, temp_project):
        provider = WorkspaceContextProvider()
        asyncio.run(provider.discover_projects(str(temp_project)))
        asyncio.run(provider.build_graph(str(temp_project)))
        ctx = provider.get_project_context(str(temp_project))
        assert "root" in ctx
        assert ctx["root"] == str(temp_project)
        assert ctx["stats"]["total_files"] >= 1

    def test_get_workspace_context(self, temp_project):
        provider = WorkspaceContextProvider()
        asyncio.run(provider.discover_projects(str(temp_project)))
        ctx = provider.get_workspace_context()
        assert ctx["project_count"] >= 1
        assert len(ctx["projects"]) >= 1
        assert ctx["projects"][0]["name"] == temp_project.name

    def test_resolve_project(self, temp_project):
        provider = WorkspaceContextProvider()
        asyncio.run(provider.discover_projects(str(temp_project)))
        test_file = str(temp_project / "src" / "main.py")
        project = provider._resolve_project(test_file)
        assert project is not None
        assert project.path == str(temp_project)


class TestWorkspaceAwareCapabilityResolver:
    def test_resolve_adds_workspace_capabilities(self):
        resolver = WorkspaceAwareCapabilityResolver()
        result = resolver.resolve("Filesystem Action", ["General"])
        assert "Workspace" in result
        assert "WorkspaceAnalysis" in result
        assert "CodeSearch" in result

    def test_resolve_does_not_add_for_other_intents(self):
        resolver = WorkspaceAwareCapabilityResolver()
        result = resolver.resolve("Conversation", ["General"])
        assert "Workspace" not in result

    def test_resolve_preserves_base_capabilities(self):
        resolver = WorkspaceAwareCapabilityResolver()
        result = resolver.resolve("Tool Invocation", ["General", "Planning"])
        assert "General" in result
        assert "Planning" in result
        assert "Workspace" in result


class TestKnowledgeIntegration:
    def test_initialization(self):
        mock_km = MagicMock()
        ki = KnowledgeIntegration(mock_km)
        assert ki.indexed_count == 0

    def test_index_file(self):
        mock_km = MagicMock()
        mock_km.index_file = AsyncMock(return_value=None)
        ki = KnowledgeIntegration(mock_km)

        result = asyncio.run(ki.index_file("/tmp/test.py"))
        assert result is True
        assert ki.indexed_count == 1

    def test_index_file_failure(self):
        mock_km = MagicMock()
        mock_km.index_file = AsyncMock(side_effect=Exception("fail"))
        ki = KnowledgeIntegration(mock_km)

        result = asyncio.run(ki.index_file("/tmp/test.py"))
        assert result is False

    def test_remove_file(self):
        mock_km = MagicMock()
        mock_km.delete_document = AsyncMock(return_value=None)
        ki = KnowledgeIntegration(mock_km)

        result = asyncio.run(ki.remove_file("/tmp/test.py"))
        assert result is True

    def test_index_project_files(self, temp_project):
        mock_km = MagicMock()
        mock_km.index_file = AsyncMock(return_value=None)
        ki = KnowledgeIntegration(mock_km)

        scanner = WorkspaceScanner()
        project = scanner._build_project_root(str(temp_project))
        graph = scanner.scan_project(project)

        count = asyncio.run(ki.index_project_files(graph))
        assert count >= 1
        assert ki.indexed_count == count


# ── Model Tests ───────────────────────────────────────────────────────────

class TestModels:
    def test_project_root_defaults(self):
        pr = ProjectRoot(path="/tmp/test", name="test")
        assert pr.is_git is False
        assert pr.branch is None
        assert pr.file_count == 0
        assert len(pr.technologies) == 0

    def test_project_root_with_attributes(self):
        pr = ProjectRoot(
            path="/tmp/test", name="test",
            is_git=True, branch="develop",
            file_count=10,
            technologies={Technology.PYTHON, Technology.JAVASCRIPT},
        )
        assert pr.is_git is True
        assert pr.branch == "develop"
        assert Technology.PYTHON in pr.technologies

    def test_file_node_extension(self):
        node = FileNode(
            path="/tmp/test/main.py", name="main.py",
            extension=".py", size=100, mtime=0.0, sha256="",
        )
        assert node.extension == ".py"

    def test_file_node_no_extension(self):
        node = FileNode(
            path="/tmp/test/Dockerfile", name="Dockerfile",
            extension="(no ext)", size=100, mtime=0.0, sha256="",
        )
        assert node.extension == "(no ext)"

    def test_project_graph_add_file(self):
        graph = ProjectGraph(root="/tmp", name="test")
        node = FileNode(
            path="/tmp/main.py", name="main.py",
            extension=".py", size=100, mtime=0.0, sha256="",
        )
        graph.add_file(node)
        assert len(graph.files) == 1
        assert "/tmp/main.py" in graph.files

    def test_project_graph_deduplicates(self):
        graph = ProjectGraph(root="/tmp", name="test")
        node1 = FileNode(
            path="/tmp/main.py", name="main.py",
            extension=".py", size=100, mtime=0.0, sha256="",
        )
        node2 = FileNode(
            path="/tmp/main.py", name="main.py",
            extension=".py", size=200, mtime=1.0, sha256="",
        )
        graph.add_file(node1)
        graph.add_file(node2)
        assert len(graph.files) == 1

    def test_graph_stats_empty(self):
        graph = ProjectGraph(root="/tmp", name="test")
        stats = graph.stats()
        assert stats.total_files == 0
        assert stats.total_modules == 0
        assert stats.total_imports == 0
        assert stats.entry_points == 0
        assert stats.files_by_extension == {}

    def test_module_node(self):
        mod = ModuleNode(name="src", root_path="/tmp/src", is_package=True)
        assert mod.name == "src"
        assert mod.is_package is True
        assert len(mod.files) == 0
        mod.files.append("/tmp/src/main.py")
        assert len(mod.files) == 1

    def test_import_edge(self):
        edge = ImportEdge(source="/tmp/src/main.py", target="os")
        assert edge.source == "/tmp/src/main.py"
        assert edge.target == "os"
        assert edge.import_type == "explicit"

    def test_technology_enum_values(self):
        assert Technology.PYTHON.value == "python"
        assert Technology.JAVASCRIPT.value == "javascript"
        assert Technology.TYPESCRIPT.value == "typescript"
        assert Technology.GO.value == "go"
        assert Technology.RUST.value == "rust"
