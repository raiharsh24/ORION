import os
import time
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from loguru import logger

from app.plugin_marketplace.base import (
    CacheEntry, MarketplaceConfig,
)


class PackageCache:
    def __init__(self, config: MarketplaceConfig) -> None:
        self._config = config
        self._cache_dir = Path(config.cache_path)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get(self, plugin_id: str, version: str) -> Optional[str]:
        key = f"{plugin_id}@{version}"
        entry = self._index.get(key)
        if entry is None:
            path = self._cache_dir / f"{key}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    entry = CacheEntry(
                        plugin_id=data["plugin_id"],
                        version=data["version"],
                        cache_path=str(path),
                        cached_at=datetime.fromisoformat(data["cached_at"]),
                        size_bytes=data["size_bytes"],
                        integrity_hash=data.get("integrity_hash", ""),
                        access_count=data.get("access_count", 0),
                    )
                    self._index[key] = entry
                except Exception:
                    self._misses += 1
                    return None
            else:
                self._misses += 1
                return None

        entry.access_count += 1
        entry.last_accessed = datetime.now(timezone.utc)
        self._hits += 1
        return entry.cache_path

    def put(self, plugin_id: str, version: str, data: Dict[str, Any],
            integrity_hash: str = "") -> str:
        key = f"{plugin_id}@{version}"
        path = self._cache_dir / f"{key}.json"
        cache_data = {
            "plugin_id": plugin_id,
            "version": version,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(json.dumps(data)),
            "integrity_hash": integrity_hash,
            "access_count": 0,
            "data": data,
        }
        path.write_text(json.dumps(cache_data, indent=2))
        entry = CacheEntry(
            plugin_id=plugin_id,
            version=version,
            cache_path=str(path),
            cached_at=datetime.now(timezone.utc),
            size_bytes=cache_data["size_bytes"],
            integrity_hash=integrity_hash,
        )
        self._index[key] = entry
        self._evict_if_needed()
        return str(path)

    def remove(self, plugin_id: str, version: str) -> bool:
        key = f"{plugin_id}@{version}"
        entry = self._index.pop(key, None)
        if entry:
            path = Path(entry.cache_path)
            if path.exists():
                path.unlink()
            return True
        path = self._cache_dir / f"{key}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def clear(self) -> int:
        count = 0
        for path in self._cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        self._index.clear()
        self._hits = 0
        self._misses = 0
        return count

    def get_statistics(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        total_size = sum(
            p.stat().st_size for p in self._cache_dir.glob("*.json")
        )
        return {
            "entries": len(self._index),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "size_bytes": total_size,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "cache_path": str(self._cache_dir),
        }

    def _evict_if_needed(self) -> None:
        max_bytes = int(self._config.max_cache_size_mb * 1024 * 1024)
        total = sum(p.stat().st_size for p in self._cache_dir.glob("*.json"))
        if total <= max_bytes:
            return
        entries = sorted(
            self._index.values(),
            key=lambda e: (e.access_count, e.last_accessed or e.cached_at),
        )
        while total > max_bytes and entries:
            entry = entries.pop(0)
            path = Path(entry.cache_path)
            if path.exists():
                total -= path.stat().st_size
                path.unlink()
            self._index.pop(f"{entry.plugin_id}@{entry.version}", None)
