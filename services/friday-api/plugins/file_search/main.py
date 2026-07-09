import fnmatch
from pathlib import Path

from app.plugin_sdk.base_plugin import BasePlugin


class FileSearchPlugin(BasePlugin):
    id = "file_search"
    name = "File Search"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("File Search loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["filesystem.read"]

    def search_by_name(self, pattern: str, root_dir: str = ".") -> list:
        matches = []
        root = Path(root_dir).resolve()
        for path in root.rglob(pattern):
            matches.append(str(path.relative_to(root)))
        self.log_info(f"Found {len(matches)} files matching '{pattern}'")
        return matches

    def search_by_content(self, text: str, root_dir: str = ".", glob_pattern: str = "*") -> list:
        matches = []
        root = Path(root_dir).resolve()
        for path in root.rglob(glob_pattern):
            if not path.is_file():
                continue
            try:
                content = path.read_text(errors="ignore")
                if text.lower() in content.lower():
                    matches.append(str(path.relative_to(root)))
            except Exception:
                continue
        self.log_info(f"Found {len(matches)} files containing '{text}'")
        return matches
