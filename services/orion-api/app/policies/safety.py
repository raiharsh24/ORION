import re
from typing import List, Set

BLACKLISTED_COMMANDS: Set[str] = {
    "rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777 /",
    "> /dev/sda", "wget http://", "curl http://",
}

BLACKLISTED_PATTERNS: List[str] = [
    r"\brm\s+-rf\s+/",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bchmod\s+777\s+/",
    r">\s*/dev/sd",
    r"\bwget\s+http://",
    r"\bcurl\s+http://",
]

BLOCKED_PATHS_PREFIXES: Set[str] = {
    "/etc", "/boot", "/sys", "/proc", "/dev",
    "/usr/lib", "/usr/bin", "/usr/sbin",
    "/bin", "/sbin",
}


class SafetyPolicy:
    """
    Validates automation commands against system safety rules.
    """
    def __init__(self) -> None:
        pass

    async def is_safe(self, command: str) -> bool:
        cmd_normalized = " ".join(command.split()).lower()
        for blacklisted in BLACKLISTED_COMMANDS:
            if blacklisted in cmd_normalized:
                return False
        for pattern in BLACKLISTED_PATTERNS:
            if re.search(pattern, command):
                return False
        return True

    def is_path_safe(self, path: str) -> bool:
        import os
        abs_path = os.path.abspath(path)
        for prefix in BLOCKED_PATHS_PREFIXES:
            if abs_path.startswith(prefix):
                return False
        return True
