import os
import re
from typing import Dict, Any, Optional
from loguru import logger

class SandboxViolation(Exception):
    """Exception thrown on sandbox policy rules violation."""
    pass

class SandboxManager:
    """
    Validates filesystem boundaries and flags command line injection patterns.
    """
    def __init__(self, workspace_root: Optional[str] = None) -> None:
        # Resolve absolute workspace path
        self._workspace_root = os.path.abspath(workspace_root or os.getcwd())
        self._blacklisted_patterns = [
            r"\brm\s+-rf\s+/",
            r"\bmkfs\b",
            r"\bdd\s+if=",
            r"\bshred\b",
            r"\bchmod\s+-R\s+777\b"
        ]

    def validate_command(self, cmd: str) -> None:
        cmd_lower = cmd.lower()
        for pattern in self._blacklisted_patterns:
            if re.search(pattern, cmd_lower):
                logger.error(f"SandboxManager violation: command pattern '{pattern}' matched in '{cmd}'")
                raise SandboxViolation(f"Security Sandbox: Command execution blocked by policy rules.")

    def validate_path(self, path: str) -> None:
        if not path:
            return
        abs_path = os.path.abspath(path)
        
        # Permit if inside workspace root
        if abs_path.startswith(self._workspace_root):
            return
            
        # Permit if inside system temporary directory
        import tempfile
        sys_temp = os.path.abspath(tempfile.gettempdir())
        if abs_path.startswith(sys_temp):
            return

        logger.error(f"SandboxManager violation: path '{abs_path}' falls outside workspace '{self._workspace_root}' and temp '{sys_temp}'")
        raise SandboxViolation("Security Sandbox: Path access restricted to workspace folder bounds.")
