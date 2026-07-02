from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple

from app.intent.types import IntentType


class CacheLevel(str, Enum):
    CONVERSATION = "conversation"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    WORKFLOW = "workflow"
    DESKTOP = "desktop"
    MISSION = "mission"
    TOOL_RESULTS = "tool_results"
    RANKING_RESULTS = "ranking_results"
    COMPRESSED_CONTEXT = "compressed_context"


CACHE_LEVELS_LIST = [
    CacheLevel.CONVERSATION,
    CacheLevel.MEMORY,
    CacheLevel.KNOWLEDGE,
    CacheLevel.WORKFLOW,
    CacheLevel.DESKTOP,
    CacheLevel.MISSION,
    CacheLevel.TOOL_RESULTS,
    CacheLevel.RANKING_RESULTS,
    CacheLevel.COMPRESSED_CONTEXT,
]


@dataclass(frozen=True)
class CacheKey:
    session_id: str = ""
    intent: str = ""
    strategy: str = ""
    provider: str = ""
    extractor: str = ""
    version: str = "1"
    context_hash: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "session_id": self.session_id,
            "intent": self.intent,
            "strategy": self.strategy,
            "provider": self.provider,
            "extractor": self.extractor,
            "version": self.version,
            "context_hash": self.context_hash,
        }


@dataclass
class CacheEntry:
    key: CacheKey
    value: Any = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: float = 300.0
    priority: bool = False
    pinned: bool = False
    size: int = 0
    access_count: int = 0
    level: str = ""

    @property
    def expired(self) -> bool:
        if self.ttl_seconds <= 0:
            return False
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.total_seconds() > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.accessed_at).total_seconds()


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    stores: int = 0
    evictions: int = 0
    expirations: int = 0
    invalidations: int = 0
    memory_usage: int = 0
    average_lookup_ms: float = 0.0
    average_insert_ms: float = 0.0
    total_lookups: int = 0
    total_inserts: int = 0
    entries_count: int = 0
    pinned_entries: int = 0
    per_level: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total > 0 else 0.0

    @property
    def miss_ratio(self) -> float:
        total = self.hits + self.misses
        return round(self.misses / total, 4) if total > 0 else 0.0


@dataclass
class CacheInvalidationPolicy:
    on_memory_change: bool = True
    on_desktop_change: bool = True
    on_workflow_change: bool = True
    on_tool_output_change: bool = True
    on_knowledge_update: bool = True
    on_conversation_reset: bool = True
    on_model_change: bool = True
    on_strategy_change: bool = True


DEFAULT_INVALIDATION_POLICY = CacheInvalidationPolicy()


DEFAULT_CACHE_TTL: Dict[CacheLevel, float] = {
    CacheLevel.CONVERSATION: 120.0,
    CacheLevel.MEMORY: 300.0,
    CacheLevel.KNOWLEDGE: 600.0,
    CacheLevel.WORKFLOW: 60.0,
    CacheLevel.DESKTOP: 30.0,
    CacheLevel.MISSION: 120.0,
    CacheLevel.TOOL_RESULTS: 300.0,
    CacheLevel.RANKING_RESULTS: 600.0,
    CacheLevel.COMPRESSED_CONTEXT: 600.0,
}


DEFAULT_CACHE_LIMITS: Dict[CacheLevel, int] = {
    CacheLevel.CONVERSATION: 100,
    CacheLevel.MEMORY: 200,
    CacheLevel.KNOWLEDGE: 200,
    CacheLevel.WORKFLOW: 50,
    CacheLevel.DESKTOP: 50,
    CacheLevel.MISSION: 100,
    CacheLevel.TOOL_RESULTS: 100,
    CacheLevel.RANKING_RESULTS: 100,
    CacheLevel.COMPRESSED_CONTEXT: 100,
}


def compute_context_hash(content: Any) -> str:
    import hashlib, json
    try:
        raw = json.dumps(content, sort_keys=True, default=str)
    except Exception:
        raw = str(content)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


class IContextCache(ABC):

    @property
    @abstractmethod
    def cache_name(self) -> str:
        ...

    @abstractmethod
    async def get(self, key: CacheKey, level: CacheLevel = CacheLevel.CONVERSATION) -> Optional[CacheEntry]:
        ...

    @abstractmethod
    async def set(self, key: CacheKey, value: Any, level: CacheLevel = CacheLevel.CONVERSATION,
                  ttl_seconds: Optional[float] = None, priority: bool = False,
                  pinned: bool = False) -> None:
        ...

    @abstractmethod
    async def invalidate(self, pattern: Optional[Dict[str, str]] = None,
                         level: Optional[CacheLevel] = None) -> int:
        ...

    @abstractmethod
    async def invalidate_level(self, level: CacheLevel) -> int:
        ...

    @abstractmethod
    async def clear(self) -> None:
        ...

    @abstractmethod
    async def cleanup(self) -> int:
        ...

    @abstractmethod
    def metrics(self) -> CacheMetrics:
        ...

    @abstractmethod
    def get_entry_count(self, level: Optional[CacheLevel] = None) -> int:
        ...
