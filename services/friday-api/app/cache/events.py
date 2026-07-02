from typing import Dict, Any, Optional
from app.events.events import FridayEvent


class CacheHit(FridayEvent):
    def __init__(self, level: str = "", key: Optional[Dict[str, str]] = None,
                 age_seconds: float = 0.0, size: int = 0) -> None:
        super().__init__(topic="CacheHit", data={
            "level": level,
            "key": key or {},
            "age_seconds": age_seconds,
            "size": size,
        })


class CacheMiss(FridayEvent):
    def __init__(self, level: str = "", key: Optional[Dict[str, str]] = None) -> None:
        super().__init__(topic="CacheMiss", data={
            "level": level,
            "key": key or {},
        })


class CacheStore(FridayEvent):
    def __init__(self, level: str = "", key: Optional[Dict[str, str]] = None,
                 size: int = 0, ttl_seconds: float = 0.0) -> None:
        super().__init__(topic="CacheStore", data={
            "level": level,
            "key": key or {},
            "size": size,
            "ttl_seconds": ttl_seconds,
        })


class CacheInvalidate(FridayEvent):
    def __init__(self, level: str = "", reason: str = "",
                 entries_removed: int = 0) -> None:
        super().__init__(topic="CacheInvalidate", data={
            "level": level,
            "reason": reason,
            "entries_removed": entries_removed,
        })


class CacheExpired(FridayEvent):
    def __init__(self, level: str = "", entries_removed: int = 0) -> None:
        super().__init__(topic="CacheExpired", data={
            "level": level,
            "entries_removed": entries_removed,
        })
