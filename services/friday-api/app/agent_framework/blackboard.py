import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

from app.agent_framework.locks import KeyLockManager


@dataclass
class BlackboardEntry:
    key: str
    value: Any
    version: int
    timestamp: float
    writer: str = ""


@dataclass
class BlackboardHealth:
    status: str = "healthy"
    entries: int = 0
    locked_keys: int = 0
    working_memory_entries: int = 0


class Blackboard:
    def __init__(self, lock_manager: Optional[KeyLockManager] = None):
        self._entries: Dict[str, BlackboardEntry] = {}
        self._history: Dict[str, List[BlackboardEntry]] = {}
        self._working_memory: Dict[str, Any] = {}
        self._lock_manager = lock_manager or KeyLockManager()
        self._update_callback: Optional[Callable[[str, Any, str], None]] = None

    def set_update_callback(self, callback: Callable[[str, Any, str], None]) -> None:
        self._update_callback = callback

    async def post(self, key: str, value: Any, writer: str = "",
                   acquire_lock: bool = True) -> int:
        version = self._entries[key].version + 1 if key in self._entries else 1
        entry = BlackboardEntry(
            key=key, value=value, version=version,
            timestamp=time.time(), writer=writer,
        )
        self._entries[key] = entry
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(entry)
        if self._update_callback:
            self._update_callback(key, value, writer)
        return version

    async def read(self, key: str) -> Optional[Any]:
        entry = self._entries.get(key)
        return entry.value if entry else None

    async def read_with_meta(self, key: str) -> Optional[BlackboardEntry]:
        return self._entries.get(key)

    async def delete(self, key: str) -> bool:
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def get_version(self, key: str) -> int:
        entry = self._entries.get(key)
        return entry.version if entry else 0

    def get_history(self, key: str) -> List[BlackboardEntry]:
        return self._history.get(key, [])

    def check_conflict(self, key: str, expected_version: int) -> bool:
        return self.get_version(key) != expected_version

    def get_all_keys(self) -> List[str]:
        return list(self._entries.keys())

    def get_all_entries(self) -> Dict[str, BlackboardEntry]:
        return dict(self._entries)

    async def set_working(self, key: str, value: Any) -> None:
        self._working_memory[key] = value

    def get_working(self, key: str) -> Optional[Any]:
        return self._working_memory.get(key)

    def clear_working(self) -> None:
        self._working_memory.clear()

    def health(self) -> BlackboardHealth:
        return BlackboardHealth(
            status="healthy",
            entries=len(self._entries),
            locked_keys=self._lock_manager.locked_count(),
            working_memory_entries=len(self._working_memory),
        )
