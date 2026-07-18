import os
import subprocess
import json
import time
from typing import Dict, List, Optional, Set
from pathlib import Path

from app.workspace.models import (
    Technology, FileNode, ProjectRoot, ProjectGraph, WorkspaceContext,
)

_LANGUAGE_EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go",
    ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby",
    ".php": "PHP", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++",
    ".cs": "C#", ".swift": "Swift", ".scala": "Scala",
    ".ex": "Elixir", ".exs": "Elixir", ".vue": "Vue", ".svelte": "Svelte",
    ".css": "CSS", ".scss": "SCSS", ".less": "Less", ".html": "HTML",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".json": "JSON",
    ".md": "Markdown", ".sql": "SQL", ".r": "R", ".dart": "Dart",
    ".lua": "Lua",
}

_PACKAGE_MANAGER_FILES = {
    "package-lock.json": "npm", "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm", "bun.lockb": "bun",
    "Cargo.lock": "cargo", "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv", "Gemfile.lock": "bundler",
    "go.sum": "go", "mix.lock": "mix", "composer.lock": "composer",
    "gradle.lockfile": "gradle",
}

_BUILD_SYSTEM_FILES = {
    "Makefile": "make", "CMakeLists.txt": "cmake",
    "build.gradle": "gradle", "pom.xml": "maven",
    "Cargo.toml": "cargo", "webpack.config.js": "webpack",
    "vite.config.ts": "vite", "vite.config.js": "vite",
    "next.config.js": "next.js", "nuxt.config.ts": "nuxt",
    "tsconfig.json": "typescript", "Rakefile": "rake",
}

_FRAMEWORK_DETECTORS = [
    ("react", {"package.json": lambda d: _has_dep(d, "react")}),
    ("vue", {"package.json": lambda d: _has_dep(d, "vue")}),
    ("angular", {"package.json": lambda d: _has_dep(d, "@angular/core")}),
    ("svelte", {"package.json": lambda d: _has_dep(d, "svelte")}),
    ("next.js", {"package.json": lambda d: _has_dep(d, "next")}),
    ("nuxt", {"package.json": lambda d: _has_dep(d, "nuxt")}),
    ("express", {"package.json": lambda d: _has_dep(d, "express")}),
    ("django", {"manage.py": lambda _: True}),
    ("flask", {"requirements.txt": lambda c: "flask" in c.lower() if c else False}),
    ("fastapi", {"requirements.txt": lambda c: "fastapi" in c.lower() if c else False}),
    ("spring", {"pom.xml": lambda c: "spring" in c.lower() if c else False}),
    ("rails", {"Gemfile": lambda c: "rails" in c.lower() if c else False}),
    ("rocket", {"Cargo.toml": lambda c: "rocket" in c.lower() if c else False}),
    ("axum", {"Cargo.toml": lambda c: "axum" in c.lower() if c else False}),
    ("gin", {"go.mod": lambda c: "gin" in c.lower() if c else False}),
]

_PROJECT_TYPES = {
    ("react", "next.js"): "frontend", ("vue", "nuxt"): "frontend",
    ("angular",): "frontend", ("svelte",): "frontend",
    ("django", "flask", "fastapi"): "backend",
    ("express",): "backend", ("rails",): "backend",
    ("spring",): "backend", ("next.js", "nuxt"): "fullstack",
}

_EXT_TO_TECH: Dict[str, Technology] = {
    ".py": Technology.PYTHON, ".js": Technology.JAVASCRIPT,
    ".jsx": Technology.JAVASCRIPT, ".ts": Technology.TYPESCRIPT,
    ".tsx": Technology.TYPESCRIPT, ".go": Technology.GO,
    ".rs": Technology.RUST, ".java": Technology.JAVA,
    ".kt": Technology.KOTLIN, ".rb": Technology.RUBY,
    ".php": Technology.PHP, ".cs": Technology.CSHARP,
    ".swift": Technology.SWIFT, ".scala": Technology.SCALA,
    ".ex": Technology.ELIXIR, ".exs": Technology.ELIXIR,
    ".dart": Technology.DART, ".sh": Technology.SHELL,
    ".bash": Technology.SHELL, ".sql": Technology.SQL,
    ".css": Technology.CSS, ".scss": Technology.CSS,
    ".html": Technology.HTML,
}

_IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".pytest_cache", "dist", "build", "target", ".next",
    ".cache", ".idea", ".vscode", ".mypy_cache", ".ruff_cache",
    "site-packages", ".tox", ".eggs", "*.egg-info",
}


def _has_dep(pkg_data: dict, name: str) -> bool:
    deps = pkg_data.get("dependencies", {})
    dev_deps = pkg_data.get("devDependencies", {})
    return name in deps or name in dev_deps


def _run_git_command(args: List[str], cwd: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _detect_framework(root: str) -> str:
    root_path = Path(root)
    for framework_name, detectors in _FRAMEWORK_DETECTORS:
        for filename, detector_fn in detectors.items():
            fp = root_path / filename
            if fp.is_file():
                try:
                    if filename == "package.json":
                        with open(fp) as f:
                            data = json.load(f)
                        if detector_fn(data):
                            return framework_name
                    elif filename in ("requirements.txt", "Gemfile", "go.mod"):
                        content = fp.read_text(encoding="utf-8", errors="ignore")
                        if detector_fn(content):
                            return framework_name
                    else:
                        return framework_name
                except Exception:
                    continue
    return ""


def _detect_project_type(framework: str) -> str:
    if not framework:
        return "unknown"
    for type_keywords, ptype in _PROJECT_TYPES.items():
        if framework in type_keywords:
            return ptype
    return "library"


class WorkspaceScanner:
    def __init__(self, workspace_dir: Optional[str] = None) -> None:
        self._workspace_dir = workspace_dir or os.getcwd()
        self._context: Optional[WorkspaceContext] = None

    @property
    def root_dir(self) -> str:
        return self._workspace_dir

    @property
    def context(self) -> Optional[WorkspaceContext]:
        return self._context

    # ── New scan API ────────────────────────────────────────────────────

    def scan(self) -> WorkspaceContext:
        cwd = self._workspace_dir
        ctx = WorkspaceContext()
        ctx.current_working_directory = cwd
        ctx.current_project = os.path.basename(cwd)

        branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
        if branch:
            ctx.current_git_branch = branch
            top_level = _run_git_command(["rev-parse", "--show-toplevel"], cwd)
            if top_level:
                ctx.current_project = os.path.basename(top_level)

        scanned = self._scan_directory(cwd)
        ctx.detected_languages = scanned["languages"]
        ctx.package_managers = scanned["package_managers"]
        ctx.build_system = scanned["build_system"]
        ctx.framework = scanned["framework"]
        ctx.project_type = scanned["project_type"]
        ctx.recently_modified_files = scanned["recent_files"]
        ctx.last_updated = time.time()

        self._context = ctx
        return ctx

    def rescan(self) -> WorkspaceContext:
        return self.scan()

    # ── Original scan API (for graph.py, integration.py, tests) ────────

    def discover_roots(self, scan_path: Optional[str] = None) -> List[ProjectRoot]:
        path = scan_path or self._workspace_dir
        if not os.path.isdir(path):
            return []
        return [self._build_project_root(path)]

    def _build_project_root(self, path: str) -> ProjectRoot:
        path = os.path.abspath(path)
        name = os.path.basename(path)

        is_git = os.path.isdir(os.path.join(path, ".git"))
        branch = None
        if is_git:
            branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], path)
            if not branch:
                git_head = os.path.join(path, ".git", "HEAD")
                try:
                    with open(git_head) as f:
                        content = f.read().strip()
                    if content.startswith("ref: refs/heads/"):
                        branch = content.split("refs/heads/")[-1]
                except OSError:
                    pass

        technologies = self._detect_technologies(path)

        file_count = 0
        for root, dirs, _ in os.walk(path):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for fname in os.listdir(root):
                fp = os.path.join(root, fname)
                if os.path.isfile(fp):
                    file_count += 1

        return ProjectRoot(
            path=path, name=name, is_git=is_git,
            branch=branch, file_count=file_count,
            technologies=technologies,
        )

    def _detect_technologies(self, path: str) -> Set[Technology]:
        techs: Set[Technology] = set()
        root_path = Path(path)
        if not root_path.is_dir():
            return techs

        for entry in root_path.rglob("*"):
            if entry.is_file():
                ext = entry.suffix.lower()
                if ext in _EXT_TO_TECH:
                    techs.add(_EXT_TO_TECH[ext])

        # Detect from config files even without source file extensions
        if (root_path / "package.json").is_file():
            techs.add(Technology.JAVASCRIPT)
        if (root_path / "requirements.txt").is_file() or (root_path / "setup.py").is_file() or (root_path / "pyproject.toml").is_file():
            techs.add(Technology.PYTHON)
        if (root_path / "go.mod").is_file():
            techs.add(Technology.GO)
        if (root_path / "Cargo.toml").is_file():
            techs.add(Technology.RUST)

        return techs

    def scan_project(
        self,
        project: ProjectRoot,
        compute_imports: bool = True,
    ) -> ProjectGraph:
        from app.workspace.graph import GraphBuilder

        builder = GraphBuilder(project.path, project.name)
        files: Dict[str, FileNode] = {}

        for root, dirs, fnames in os.walk(project.path):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for fname in fnames:
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower() or "(no ext)"
                try:
                    stat = os.stat(fpath)
                except OSError:
                    continue
                node = FileNode(
                    path=fpath, name=fname, extension=ext,
                    size=stat.st_size, mtime=stat.st_mtime,
                    sha256="",
                )
                files[fpath] = node

        graph = builder.build(files, project.technologies)
        return graph

    # ── Internal helpers ───────────────────────────────────────────────

    def _scan_directory(self, root: str, max_files: int = 500) -> dict:
        result = {
            "languages": [], "package_managers": [],
            "build_system": "", "framework": "",
            "project_type": "", "recent_files": [],
        }

        root_path = Path(root)
        if not root_path.is_dir():
            return result

        lang_set: Set[str] = set()
        recent_cutoff = time.time() - 300
        file_count = 0

        for entry in root_path.rglob("*"):
            if file_count >= max_files:
                break
            if entry.is_file() and not entry.name.startswith("."):
                file_count += 1
                ext = entry.suffix.lower()
                if ext in _LANGUAGE_EXTENSIONS:
                    lang_set.add(_LANGUAGE_EXTENSIONS[ext])

                name = entry.name
                if name in _PACKAGE_MANAGER_FILES:
                    pm = _PACKAGE_MANAGER_FILES[name]
                    if pm not in result["package_managers"]:
                        result["package_managers"].append(pm)

                if name in _BUILD_SYSTEM_FILES and not result["build_system"]:
                    result["build_system"] = _BUILD_SYSTEM_FILES[name]

                try:
                    if entry.stat().st_mtime > recent_cutoff:
                        result["recent_files"].append(str(entry))
                except OSError:
                    pass

        result["languages"] = sorted(lang_set)
        result["framework"] = _detect_framework(root)
        result["project_type"] = _detect_project_type(result["framework"])

        if not result["project_type"] and result["languages"]:
            result["project_type"] = "unknown"

        result["recent_files"] = result["recent_files"][:20]
        return result
