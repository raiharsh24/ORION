import os
from typing import List, Dict, Any, Optional
from loguru import logger

class WorkspaceManager:
    """
    Scans and manages local directories to discover repositories and projects.
    """
    def __init__(self, root_dir: str = "/home/warlock/ORION") -> None:
        self.root_dir = os.path.abspath(root_dir)
        self.ignore_folders = {
            ".git", "node_modules", ".venv", "venv", "__pycache__", 
            ".pytest_cache", "dist", "build", "target", ".next", ".cache"
        }

    def _get_git_branch(self, git_dir: str) -> Optional[str]:
        """
        Extracts current Git branch by reading HEAD file.
        Fails safely without launching terminal commands.
        """
        head_path = os.path.join(git_dir, "HEAD")
        if os.path.exists(head_path):
            try:
                with open(head_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.startswith("ref:"):
                        return content.split("/")[-1]
                    return content[:8]  # Returns short commit SHA
            except Exception as e:
                logger.warning(f"Failed to read Git HEAD at {head_path}: {str(e)}")
        return None

    def _count_files(self, path: str) -> int:
        """Counts files in directory recursively up to safety cap of 1000."""
        count = 0
        for root, dirs, files in os.walk(path):
            # Prune directories in-place
            dirs[:] = [d for d in dirs if d not in self.ignore_folders]
            count += len(files)
            if count > 1000:
                return 1000
        return count

    def discover_projects(self, scan_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Walks directory recursively up to depth of 3 to list Git repos and local projects.
        """
        target_path = os.path.abspath(scan_path) if scan_path else self.root_dir
        if not os.path.exists(target_path) or not os.path.isdir(target_path):
            logger.error(f"Workspace path {target_path} is invalid.")
            return []

        projects = []
        base_depth = target_path.count(os.sep)

        # Check if the target root itself contains git/projects
        git_dir = os.path.join(target_path, ".git")
        if os.path.exists(git_dir):
            branch = self._get_git_branch(git_dir)
            projects.append({
                "name": os.path.basename(target_path),
                "path": target_path,
                "is_git": True,
                "branch": branch,
                "files_count": self._count_files(target_path),
                "languages": ["Python", "TypeScript", "JavaScript"] # Heuristic/nominal
            })

        for root, dirs, files in os.walk(target_path):
            depth = root.count(os.sep) - base_depth
            if depth >= 3:
                # Limit recursive search depth to maintain performance
                dirs[:] = []
                continue

            # Remove ignored folders in-place
            dirs[:] = [d for d in dirs if d not in self.ignore_folders]

            for d in list(dirs):
                project_path = os.path.join(root, d)
                git_folder = os.path.join(project_path, ".git")
                
                # Check for project boundaries
                has_git = os.path.exists(git_folder)
                has_package_json = os.path.exists(os.path.join(project_path, "package.json"))
                has_requirements = os.path.exists(os.path.join(project_path, "requirements.txt"))
                has_pyproject = os.path.exists(os.path.join(project_path, "pyproject.toml"))
                
                if has_git or has_package_json or has_requirements or has_pyproject:
                    # Remove it from further recursion to treat it as a distinct project root
                    if d in dirs:
                        dirs.remove(d)

                    branch = self._get_git_branch(git_folder) if has_git else None
                    langs = []
                    if has_package_json:
                        langs.extend(["JavaScript", "TypeScript"])
                    if has_requirements or has_pyproject:
                        langs.append("Python")
                    if not langs:
                        langs.append("Text")

                    projects.append({
                        "name": d,
                        "path": project_path,
                        "is_git": has_git,
                        "branch": branch,
                        "files_count": self._count_files(project_path),
                        "languages": list(set(langs))
                    })
        
        return projects
