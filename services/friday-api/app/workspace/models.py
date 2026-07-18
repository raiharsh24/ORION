import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set
import time


# ── Original workspace models (used by graph.py, integration.py, tests) ──

class Technology(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    KOTLIN = "kotlin"
    RUBY = "ruby"
    PHP = "php"
    CSHARP = "csharp"
    SWIFT = "swift"
    SCALA = "scala"
    ELIXIR = "elixir"
    DART = "dart"
    SHELL = "shell"
    SQL = "sql"
    CSS = "css"
    HTML = "html"
    DOCKER = "docker"
    TERRAFORM = "terraform"
    UNKNOWN = "unknown"


@dataclass
class FileNode:
    path: str
    name: str
    extension: str = ""
    size: int = 0
    mtime: float = 0.0
    sha256: str = ""
    language: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    is_entry_point: bool = False

    def __hash__(self) -> int:
        return hash(self.path)


@dataclass
class ModuleNode:
    name: str
    root_path: str
    is_package: bool = False
    files: List[str] = field(default_factory=list)


@dataclass
class ImportEdge:
    source: str
    target: str
    import_type: str = "explicit"


@dataclass
class ProjectRoot:
    path: str
    name: str
    is_git: bool = False
    branch: Optional[str] = None
    file_count: int = 0
    technologies: Set[Technology] = field(default_factory=set)


@dataclass
class GraphStats:
    total_files: int = 0
    total_modules: int = 0
    total_imports: int = 0
    entry_points: int = 0
    files_by_extension: Dict[str, int] = field(default_factory=dict)


@dataclass
class ProjectGraph:
    root: str
    name: str
    files: Dict[str, FileNode] = field(default_factory=dict)
    modules: Dict[str, ModuleNode] = field(default_factory=dict)
    imports: List[ImportEdge] = field(default_factory=list)
    technologies: Set[Technology] = field(default_factory=set)
    entry_points: List[str] = field(default_factory=list)

    def add_file(self, node: FileNode) -> None:
        norm = node.path
        self.files[norm] = node

    def stats(self) -> GraphStats:
        ext_counts: Dict[str, int] = {}
        for fpath in self.files:
            ext = os.path.splitext(fpath)[1].lower() or "(no ext)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        return GraphStats(
            total_files=len(self.files),
            total_modules=len(self.modules),
            total_imports=len(self.imports),
            entry_points=len(self.entry_points),
            files_by_extension=ext_counts,
        )


# ── New WorkspaceContext model ──

@dataclass
class WorkspaceContext:
    current_project: str = ""
    current_git_branch: str = ""
    opened_files: List[str] = field(default_factory=list)
    recently_modified_files: List[str] = field(default_factory=list)
    active_terminal: str = ""
    running_processes: List[str] = field(default_factory=list)
    current_working_directory: str = ""
    detected_languages: List[str] = field(default_factory=list)
    package_managers: List[str] = field(default_factory=list)
    build_system: str = ""
    framework: str = ""
    project_type: str = ""
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_project": self.current_project,
            "current_git_branch": self.current_git_branch,
            "opened_files": self.opened_files,
            "recently_modified_files": self.recently_modified_files,
            "active_terminal": self.active_terminal,
            "running_processes": self.running_processes,
            "current_working_directory": self.current_working_directory,
            "detected_languages": self.detected_languages,
            "package_managers": self.package_managers,
            "build_system": self.build_system,
            "framework": self.framework,
            "project_type": self.project_type,
            "last_updated": self.last_updated,
        }

    def to_context_string(self) -> str:
        parts = [
            f"Project: {self.current_project or 'unknown'}",
            f"Directory: {self.current_working_directory}",
        ]
        if self.current_git_branch:
            parts.append(f"Branch: {self.current_git_branch}")
        if self.detected_languages:
            parts.append(f"Languages: {', '.join(self.detected_languages)}")
        if self.framework:
            parts.append(f"Framework: {self.framework}")
        if self.build_system:
            parts.append(f"Build: {self.build_system}")
        if self.package_managers:
            parts.append(f"Package Manager(s): {', '.join(self.package_managers)}")
        if self.project_type:
            parts.append(f"Type: {self.project_type}")
        return " | ".join(parts)


# ── WorkspaceSummary model (from passive analysis) ──

@dataclass
class Recommendation:
    message: str
    priority: str = "medium"
    category: str = "general"

    def to_dict(self) -> Dict[str, str]:
        return {"message": self.message, "priority": self.priority, "category": self.category}


@dataclass
class WorkspaceSummary:
    project_name: str
    project_type: str = ""
    technologies: List[str] = field(default_factory=list)
    detected_frameworks: List[str] = field(default_factory=list)
    complexity: str = "unknown"
    health_score: float = 0.0
    health_label: str = "unknown"
    file_count: int = 0
    dependency_count: int = 0
    git_branch: str = ""
    repo_size_bytes: int = 0
    important_configs: List[str] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    last_analyzed: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "project_type": self.project_type,
            "technologies": self.technologies,
            "detected_frameworks": self.detected_frameworks,
            "complexity": self.complexity,
            "health_score": self.health_score,
            "health_label": self.health_label,
            "file_count": self.file_count,
            "dependency_count": self.dependency_count,
            "git_branch": self.git_branch,
            "repo_size_bytes": self.repo_size_bytes,
            "important_configs": self.important_configs,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "warnings": self.warnings,
            "last_analyzed": self.last_analyzed,
        }

