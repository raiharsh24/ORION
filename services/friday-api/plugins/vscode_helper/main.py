import subprocess
from pathlib import Path

from app.plugin_sdk.base_plugin import BasePlugin


class VSCodeHelperPlugin(BasePlugin):
    id = "vscode_helper"
    name = "VS Code Helper"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("VS Code Helper loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["terminal.execute"]

    def open_file(self, filepath: str) -> bool:
        try:
            path = Path(filepath).resolve()
            if not path.exists():
                self.log_error(f"File not found: {filepath}")
                return False
            subprocess.run(["code", str(path)], timeout=10)
            self.log_info(f"Opened {filepath} in VS Code")
            return True
        except FileNotFoundError:
            self.log_warning("VS Code (code) not found in PATH")
            return False
        except Exception as e:
            self.log_error(f"Failed to open VS Code: {e}")
            return False

    def open_folder(self, folder: str) -> bool:
        try:
            path = Path(folder).resolve()
            if not path.is_dir():
                self.log_error(f"Folder not found: {folder}")
                return False
            subprocess.run(["code", str(path)], timeout=10)
            self.log_info(f"Opened folder {folder} in VS Code")
            return True
        except FileNotFoundError:
            self.log_warning("VS Code (code) not found in PATH")
            return False
        except Exception as e:
            self.log_error(f"Failed to open folder: {e}")
            return False

    def search(self, query: str, folder: str = ".") -> bool:
        try:
            path = Path(folder).resolve()
            subprocess.run(["code", "--search", query, str(path)], timeout=10)
            self.log_info(f"Searched '{query}' in VS Code")
            return True
        except Exception:
            return self.open_folder(folder)
