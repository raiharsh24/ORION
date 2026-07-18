import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.workspace.models import (
    WorkspaceContext, WorkspaceSummary, Recommendation,
)

_IMPORTANT_CONFIGS = {
    "package.json": "Node.js project config",
    "tsconfig.json": "TypeScript configuration",
    "pyproject.toml": "Python project config",
    "setup.py": "Python setup script",
    "Cargo.toml": "Rust project config",
    "go.mod": "Go module definition",
    "Gemfile": "Ruby dependencies",
    "composer.json": "PHP dependencies",
    "Dockerfile": "Container definition",
    "docker-compose.yml": "Container orchestration",
    ".github/workflows": "CI/CD pipeline",
    ".gitlab-ci.yml": "CI/CD pipeline",
    ".env.example": "Environment template",
    ".gitignore": "Git ignore rules",
    ".pre-commit-config.yaml": "Pre-commit hooks",
    "Makefile": "Build automation",
    "webpack.config.js": "Webpack bundler config",
    "vite.config.ts": "Vite bundler config",
    "next.config.js": "Next.js config",
    "nuxt.config.ts": "Nuxt config",
    "jest.config.js": "Test config",
    ".eslintrc.js": "Linter config",
    ".eslintrc.json": "Linter config",
    ".prettierrc": "Formatter config",
    "rust-toolchain.toml": "Rust toolchain",
    "README.md": "Project documentation",
}

_HEALTH_CHECKS = [
    ("lock_file", "Lock file present", 1.0),
    ("git_ignore", ".gitignore present", 0.8),
    ("ci_config", "CI/CD config present", 0.7),
    ("lint_config", "Linter configured", 0.6),
    ("readme", "README.md present", 0.5),
]

_COMPLEXITY_THRESHOLDS = [
    (3000, "very_high"),
    (1000, "high"),
    (300, "medium"),
    (50, "low"),
]


class WorkspaceAnalyzer:
    def analyze(self, context: WorkspaceContext) -> WorkspaceSummary:
        root = Path(context.current_working_directory)
        summary = WorkspaceSummary(
            project_name=context.current_project,
            project_type=context.project_type,
            technologies=context.detected_languages,
            git_branch=context.current_git_branch,
        )

        self._detect_frameworks(context, summary)
        self._count_files(root, summary)
        self._collect_configs(root, summary)
        self._estimate_repo_size(root, summary)
        self._assess_dependencies(root, summary)
        self._compute_health(root, summary)
        self._assess_complexity(summary)
        self._generate_recommendations(root, context, summary)

        summary.last_analyzed = time.time()
        return summary

    def _detect_frameworks(
        self, context: WorkspaceContext, summary: WorkspaceSummary,
    ) -> None:
        frameworks = []
        if context.framework:
            frameworks.append(context.framework)

        for lang in context.detected_languages:
            lang_lower = lang.lower()
            if lang_lower == "python" and "python" not in str(frameworks):
                pass
            elif lang_lower == "javascript" and "javascript" not in str(frameworks):
                pass

        seen = set()
        for fw in frameworks:
            if fw not in seen:
                summary.detected_frameworks.append(fw)
                seen.add(fw)

        if not summary.detected_frameworks:
            summary.detected_frameworks = context.detected_languages[:3]

    def _count_files(
        self, root: Path, summary: WorkspaceSummary,
    ) -> None:
        count = 0
        ignore_dirs = {
            ".git", "node_modules", ".venv", "venv", "__pycache__",
            ".pytest_cache", "dist", "build", "target", ".next",
            ".cache", ".idea", ".vscode", ".mypy_cache",
        }
        try:
            for entry in root.rglob("*"):
                if entry.is_file():
                    parent_parts = entry.relative_to(root).parts
                    if any(part in ignore_dirs for part in parent_parts):
                        continue
                    count += 1
        except (PermissionError, OSError):
            pass
        summary.file_count = count

    def _collect_configs(
        self, root: Path, summary: WorkspaceSummary,
    ) -> None:
        found = []
        for name, description in _IMPORTANT_CONFIGS.items():
            target = root / name
            if target.exists():
                found.append(f"{name} ({description})")
        # Check .github/workflows as directory
        workflows_dir = root / ".github" / "workflows"
        if workflows_dir.is_dir():
            has_yaml = any(
                workflows_dir.glob("*.yml")) or any(workflows_dir.glob("*.yaml"))
            if has_yaml and ".github/workflows (CI/CD pipeline)" not in found:
                found.append(".github/workflows (CI/CD pipeline)")
        summary.important_configs = found

    def _estimate_repo_size(
        self, root: Path, summary: WorkspaceSummary,
    ) -> None:
        total = 0
        count = 0
        try:
            for entry in root.rglob("*"):
                if entry.is_file() and count < 2000:
                    try:
                        total += entry.stat().st_size
                        count += 1
                    except OSError:
                        pass
        except (PermissionError, OSError):
            pass
        summary.repo_size_bytes = total

    def _assess_dependencies(
        self, root: Path, summary: WorkspaceSummary,
    ) -> None:
        dep_count = 0
        pkg_json = root / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text())
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                dep_count = len(deps) + len(dev_deps)
            except (json.JSONDecodeError, OSError):
                pass
        summary.dependency_count = dep_count

    def _compute_health(
        self, root: Path, summary: WorkspaceSummary,
    ) -> None:
        score = 0.5
        total_weight = 0.0

        for check_id, label, weight in _HEALTH_CHECKS:
            total_weight += weight
            present = self._check_health_item(root, check_id)
            if present:
                score += weight * 0.15

        if total_weight > 0:
            score = min(1.0, score)

        if summary.dependency_count > 500:
            score -= 0.15
        elif summary.dependency_count > 200:
            score -= 0.05

        if "node_modules" not in [p.name for p in root.iterdir() if p.is_dir()]:
            pass

        if summary.repo_size_bytes > 50_000_000:
            score -= 0.1

        summary.health_score = max(0.0, min(1.0, score))
        summary.health_label = self._health_label(summary.health_score)

    def _health_label(self, score: float) -> str:
        if score >= 0.8:
            return "healthy"
        elif score >= 0.5:
            return "needs_attention"
        return "critical"

    def _check_health_item(self, root: Path, check_id: str) -> bool:
        checks = {
            "lock_file": lambda r: any(
                (r / f).exists() for f in [
                    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                    "poetry.lock", "Cargo.lock", "Gemfile.lock", "go.sum",
                ]
            ),
            "git_ignore": lambda r: (r / ".gitignore").exists(),
            "ci_config": lambda r: (
                (r / ".github").is_dir()
                or (r / ".gitlab-ci.yml").exists()
            ),
            "lint_config": lambda r: any(
                (r / f).exists() for f in [
                    ".eslintrc.js", ".eslintrc.json", ".prettierrc",
                    "rustfmt.toml", "pylintrc", ".flake8",
                ]
            ),
            "readme": lambda r: (r / "README.md").exists(),
        }
        checker = checks.get(check_id)
        if checker:
            return checker(root)
        return False

    def _assess_complexity(self, summary: WorkspaceSummary) -> None:
        for threshold, label in _COMPLEXITY_THRESHOLDS:
            if summary.file_count >= threshold:
                summary.complexity = label
                return
        summary.complexity = "very_low"

    def _generate_recommendations(
        self, root: Path, context: WorkspaceContext, summary: WorkspaceSummary,
    ) -> None:
        recs: List[Recommendation] = []
        warnings: List[str] = []

        # Dependency audit
        if summary.dependency_count > 100:
            recs.append(Recommendation(
                message=f"Run dependency audit ({summary.dependency_count} deps)",
                priority="medium",
                category="security",
            ))

        # Missing lock file
        if "npm" in context.package_managers or "yarn" in context.package_managers:
            has_lock = any(
                (root / f).exists()
                for f in ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
            )
            if not has_lock:
                recs.append(Recommendation(
                    message="Commit lock file for reproducible builds",
                    priority="high",
                    category="dependency",
                ))

        # Missing .gitignore
        if not (root / ".gitignore").exists():
            recs.append(Recommendation(
                message="Add .gitignore to exclude build artifacts",
                priority="medium",
                category="best_practice",
            ))

        # Missing CI
        has_ci = (root / ".github").is_dir() or (root / ".gitlab-ci.yml").exists()
        if not has_ci:
            recs.append(Recommendation(
                message="Set up CI/CD pipeline for automated testing",
                priority="low",
                category="infrastructure",
            ))

        # Large repo
        if summary.repo_size_bytes > 50_000_000:
            recs.append(Recommendation(
                message=f"Repository size ({summary.repo_size_bytes / 1_000_000:.0f}MB) "
                        f"is large — consider .gitignore or LFS",
                priority="medium",
                category="performance",
            ))

        # Framework-specific
        if context.framework == "react":
            recs.append(Recommendation(
                message="Consider React compiler / Forget for automatic memoization",
                priority="low",
                category="performance",
            ))
        elif context.framework in ("fastapi", "flask", "django"):
            recs.append(Recommendation(
                message="Ensure ASGI server (uvicorn) is configured for production",
                priority="medium",
                category="deployment",
            ))

        # Branch health
        if context.current_git_branch in ("main", "master"):
            recs.append(Recommendation(
                message="Working on default branch — create feature branches for changes",
                priority="low",
                category="workflow",
            ))

        # Many dependencies
        if summary.dependency_count > 300:
            warnings.append(
                f"High dependency count ({summary.dependency_count}) "
                f"may increase build times and attack surface"
            )

        # Summary health warnings
        if summary.health_score < 0.5:
            warnings.append(
                f"Project health is {summary.health_label} "
                f"(score: {summary.health_score:.2f})"
            )

        summary.recommendations = recs
        summary.warnings = warnings
