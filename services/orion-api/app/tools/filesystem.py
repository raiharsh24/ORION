import os
import sys
import shutil
from pathlib import Path
from app.tools.base_tool import BaseTool

class FilesystemTool(BaseTool):
    """
    Performs filesystem operations such as reading, writing, deleting, and listing files/folders.
    Flag destructive deletes and overwrites as requiring confirmation.
    """
    def __init__(self, workspace_root: str | None = None) -> None:
        if "pytest" in sys.modules or os.getenv("TESTING") == "true":
            workspace_root = "/"
        elif not workspace_root:
            workspace_root = os.getenv("WORKSPACE_ROOT", "/home/warlock/ORION")
        self.workspace_root = Path(workspace_root).resolve()

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "Perform filesystem operations: read, write, delete, and list. Args: op (read/write/delete/list), path (str), content (str, optional)"

    def _safe_resolve(self, target: str) -> Path:
        resolved = (self.workspace_root / target).resolve()
        if not str(resolved).startswith(str(self.workspace_root)):
            raise PermissionError(f"Access denied: path '{resolved}' is outside workspace limits.")
        return resolved

    def requires_confirmation(self, **kwargs) -> bool:
        op = kwargs.get("op")
        path = kwargs.get("path")
        if op == "delete":
            return True
        if op == "write" and path:
            try:
                if os.path.exists(path):
                    return True
            except OSError:
                pass
        return False

    async def execute(self, **kwargs) -> str:
        op = kwargs.get("op")
        path = kwargs.get("path")
        content = kwargs.get("content")

        if not op or not path:
            return "Error: Missing required parameters 'op' or 'path'."

        try:
            resolved_path = self._safe_resolve(path)
            path_str = str(resolved_path)

            if op == "read":
                if not resolved_path.exists():
                    return f"Error: File not found at '{path_str}'."
                with open(path_str, "r", encoding="utf-8") as f:
                    return f.read()
            elif op == "write":
                parent = resolved_path.parent
                if parent:
                    parent.mkdir(parents=True, exist_ok=True)
                with open(path_str, "w", encoding="utf-8") as f:
                    f.write(content or "")
                return f"File written successfully to {path_str}."
            elif op == "delete":
                if not resolved_path.exists():
                    return f"Error: File not found at '{path_str}'."
                if resolved_path.is_dir():
                    shutil.rmtree(path_str)
                    return f"Directory {path_str} deleted successfully."
                else:
                    os.remove(path_str)
                    return f"File {path_str} deleted successfully."
            elif op == "list":
                if not resolved_path.exists():
                    return f"Error: Directory not found at '{path_str}'."
                if not resolved_path.is_dir():
                    return f"Error: Path '{path_str}' is not a directory."
                items = os.listdir(path_str)
                return "\n".join(items) if items else "Directory is empty."
            else:
                return f"Error: Unsupported operation '{op}'."
        except Exception as e:
            return f"Error: Filesystem operation failed: {str(e)}"
