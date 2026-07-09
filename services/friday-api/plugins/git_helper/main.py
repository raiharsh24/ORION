import subprocess
from pathlib import Path

from app.plugin_sdk.base_plugin import BasePlugin


class GitHelperPlugin(BasePlugin):
    id = "git_helper"
    name = "Git Helper"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Git Helper loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["terminal.execute"]

    def _run(self, *args: str, cwd: str = ".") -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True, text=True, timeout=30,
                cwd=cwd,
            )
            return result.stdout.strip() or result.stderr.strip()
        except FileNotFoundError:
            return "Git not found"
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return str(e)

    def status(self, repo_path: str = ".") -> str:
        return self._run("status", cwd=repo_path)

    def log(self, repo_path: str = ".", count: int = 10) -> str:
        return self._run("log", f"--max-count={count}", "--oneline", cwd=repo_path)

    def branch(self, repo_path: str = ".") -> str:
        return self._run("branch", cwd=repo_path)

    def diff(self, repo_path: str = ".") -> str:
        return self._run("diff", cwd=repo_path)

    def commit(self, message: str, repo_path: str = ".") -> str:
        self._run("add", "-A", cwd=repo_path)
        return self._run("commit", "-m", message, cwd=repo_path)
