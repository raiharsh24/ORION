import asyncio
from typing import Dict, List


class KeyLockManager:
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, timeout: float = 30.0) -> bool:
        async with self._lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            lock = self._locks[key]
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def release(self, key: str) -> None:
        lock = self._locks.get(key)
        if lock and lock.locked():
            lock.release()

    def is_locked(self, key: str) -> bool:
        lock = self._locks.get(key)
        return lock is not None and lock.locked()

    def get_active_locks(self) -> List[str]:
        return [k for k, v in self._locks.items() if v.locked()]

    def locked_count(self) -> int:
        return len(self.get_active_locks())

    def clear(self) -> None:
        self._locks.clear()
