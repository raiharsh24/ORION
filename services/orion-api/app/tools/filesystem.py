import os
import shutil
from app.tools.base_tool import BaseTool

class FilesystemTool(BaseTool):
    """
    Performs filesystem operations such as reading, writing, deleting, and listing files/folders.
    Flag destructive deletes and overwrites as requiring confirmation.
    """
    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "Perform filesystem operations: read, write, delete, and list. Args: op (read/write/delete/list), path (str), content (str, optional)"

    def requires_confirmation(self, **kwargs) -> bool:
        op = kwargs.get("op")
        path = kwargs.get("path")
        if op == "delete":
            return True
        if op == "write" and path and os.path.exists(path):
            return True
        return False

    async def execute(self, **kwargs) -> str:
        op = kwargs.get("op")
        path = kwargs.get("path")
        content = kwargs.get("content")

        if not op or not path:
            return "Error: Missing required parameters 'op' or 'path'."

        try:
            if op == "read":
                if not os.path.exists(path):
                    return f"Error: File not found at '{path}'."
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            elif op == "write":
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content or "")
                return f"File written successfully to {path}."
            elif op == "delete":
                if not os.path.exists(path):
                    return f"Error: File not found at '{path}'."
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    return f"Directory {path} deleted successfully."
                else:
                    os.remove(path)
                    return f"File {path} deleted successfully."
            elif op == "list":
                if not os.path.exists(path):
                    return f"Error: Directory not found at '{path}'."
                if not os.path.isdir(path):
                    return f"Error: Path '{path}' is not a directory."
                items = os.listdir(path)
                return "\n".join(items) if items else "Directory is empty."
            else:
                return f"Error: Unsupported operation '{op}'."
        except Exception as e:
            return f"Error: Filesystem operation failed: {str(e)}"
