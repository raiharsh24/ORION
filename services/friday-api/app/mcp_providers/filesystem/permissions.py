import os
from pathlib import Path
from typing import Set


class PathPermissionError(PermissionError):
    def __init__(self, path: str, allowed_dir: str) -> None:
        self.path = path
        self.allowed_dir = allowed_dir
        super().__init__(
            f"Access denied: '{path}' is outside allowed directory '{allowed_dir}'"
        )


class FilesystemPermissionEnforcer:
    def __init__(self, allowed_directories: list[str] | None = None) -> None:
        self._allowed: Set[Path] = {
            Path(d).resolve() for d in (allowed_directories or ["/tmp"])
        }

    def resolve(self, path: str) -> Path:
        p = Path(path).expanduser().resolve()
        if not any(
            p == allowed or self._is_subdirectory(p, allowed)
            for allowed in self._allowed
        ):
            allowed_strs = [str(d) for d in self._allowed]
            raise PathPermissionError(str(p), ", ".join(allowed_strs))
        return p

    def allowed_directories(self) -> list[str]:
        return [str(d) for d in self._allowed]

    @staticmethod
    def _is_subdirectory(child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False
