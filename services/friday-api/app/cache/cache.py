import asyncio
import time
import hashlib
import json
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

from loguru import logger

from app.cache.base import (
    IContextCache, CacheKey, CacheEntry, CacheMetrics, CacheLevel,
    CACHE_LEVELS_LIST, DEFAULT_CACHE_TTL, DEFAULT_CACHE_LIMITS,
    CacheInvalidationPolicy, DEFAULT_INVALIDATION_POLICY,
)
from app.cache.events import (
    CacheHit, CacheMiss, CacheStore, CacheInvalidate, CacheExpired,
)
from app.events.bus import EventBus
from app.events.events import FridayEvent


class ContextCache(IContextCache):
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        ttl_overrides: Optional[Dict[CacheLevel, float]] = None,
        limit_overrides: Optional[Dict[CacheLevel, int]] = None,
        invalidation_policy: Optional[CacheInvalidationPolicy] = None,
        cleanup_interval: float = 60.0,
    ) -> None:
        self._event_bus = event_bus
        self._ttl: Dict[CacheLevel, float] = {**DEFAULT_CACHE_TTL, **(ttl_overrides or {})}
        self._limits: Dict[CacheLevel, int] = {**DEFAULT_CACHE_LIMITS, **(limit_overrides or {})}
        self._invalidation_policy = invalidation_policy or DEFAULT_INVALIDATION_POLICY
        self._cleanup_interval = cleanup_interval

        self._stores: Dict[CacheLevel, OrderedDict[str, CacheEntry]] = {
            level: OrderedDict() for level in CACHE_LEVELS_LIST
        }

        self._metrics = CacheMetrics()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        for level in CACHE_LEVELS_LIST:
            self._metrics.per_level[level.value] = {
                "hits": 0, "misses": 0, "stores": 0,
                "evictions": 0, "expirations": 0, "invalidations": 0,
                "entries": 0,
            }

    @property
    def cache_name(self) -> str:
        return "context_cache"

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._background_cleanup())
        self._subscribe_to_events()
        logger.info("Context Cache started.")

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        self._unsubscribe_from_events()
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("Context Cache shut down.")

    def health(self) -> dict:
        total_entries = sum(len(s) for s in self._stores.values())
        return {
            "status": "HEALTHY",
            "details": {
                "total_entries": total_entries,
                "hit_ratio": self._metrics.hit_ratio,
                "miss_ratio": self._metrics.miss_ratio,
                "evictions": self._metrics.evictions,
                "expirations": self._metrics.expirations,
                "invalidations": self._metrics.invalidations,
                "memory_usage": self._metrics.memory_usage,
                "pinned_entries": self._metrics.pinned_entries,
                "per_level": {
                    lv.value: {
                        "entries": self._metrics.per_level[lv.value]["entries"],
                        "hits": self._metrics.per_level[lv.value]["hits"],
                    }
                    for lv in CACHE_LEVELS_LIST
                },
            },
        }

    def _make_key_str(self, key: CacheKey, level: CacheLevel) -> str:
        return f"{level.value}:{key.session_id}:{key.intent}:{key.strategy}:{key.provider}:{key.extractor}:{key.version}:{key.context_hash}"

    async def get(self, key: CacheKey, level: CacheLevel = CacheLevel.CONVERSATION) -> Optional[CacheEntry]:
        t0 = time.time()
        key_str = self._make_key_str(key, level)
        store = self._stores[level]

        entry = store.get(key_str)
        if entry is None:
            self._metrics.misses += 1
            self._metrics.total_lookups += 1
            pl = self._metrics.per_level[level.value]
            pl["misses"] += 1
            self._metrics.average_lookup_ms = (
                (self._metrics.average_lookup_ms * (self._metrics.total_lookups - 1) +
                 (time.time() - t0) * 1000) / self._metrics.total_lookups
            )
            await self._publish(CacheMiss(level=level.value, key=key.to_dict()))
            return None

        if entry.expired:
            del store[key_str]
            self._metrics.expirations += 1
            pl = self._metrics.per_level[level.value]
            pl["expirations"] += 1
            pl["entries"] = len(store)
            self._metrics.misses += 1
            self._metrics.total_lookups += 1
            self._metrics.average_lookup_ms = (
                (self._metrics.average_lookup_ms * (self._metrics.total_lookups - 1) +
                 (time.time() - t0) * 1000) / self._metrics.total_lookups
            )
            await self._publish(CacheMiss(level=level.value, key=key.to_dict()))
            await self._publish(CacheExpired(level=level.value, entries_removed=1))
            return None

        store.move_to_end(key_str)
        entry.accessed_at = datetime.now(timezone.utc)
        entry.access_count += 1

        self._metrics.hits += 1
        self._metrics.total_lookups += 1
        pl = self._metrics.per_level[level.value]
        pl["hits"] += 1
        self._metrics.average_lookup_ms = (
            (self._metrics.average_lookup_ms * (self._metrics.total_lookups - 1) +
             (time.time() - t0) * 1000) / self._metrics.total_lookups
        )
        await self._publish(CacheHit(
            level=level.value, key=key.to_dict(),
            age_seconds=entry.age_seconds, size=entry.size,
        ))
        return entry

    async def set(self, key: CacheKey, value: Any, level: CacheLevel = CacheLevel.CONVERSATION,
                  ttl_seconds: Optional[float] = None, priority: bool = False,
                  pinned: bool = False) -> None:
        t0 = time.time()
        key_str = self._make_key_str(key, level)
        store = self._stores[level]
        limit = self._limits[level]
        effective_ttl = ttl_seconds if ttl_seconds is not None else self._ttl[level]
        size = self._estimate_size(value)

        if pinned:
            self._metrics.pinned_entries += 1

        if key_str in store:
            old = store[key_str]
            if old.pinned and not pinned:
                self._metrics.pinned_entries = max(0, self._metrics.pinned_entries - 1)
            if old.pinned:
                self._metrics.pinned_entries = max(0, self._metrics.pinned_entries - 1)
            store.pop(key_str)

        while len(store) >= limit:
            if not self._evict_one(store, level):
                break

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=effective_ttl,
            priority=priority,
            pinned=pinned,
            size=size,
            level=level.value,
        )
        store[key_str] = entry
        self._metrics.stores += 1
        self._metrics.total_inserts += 1
        self._metrics.memory_usage += size
        pl = self._metrics.per_level[level.value]
        pl["stores"] += 1
        pl["entries"] = len(store)
        self._metrics.average_insert_ms = (
            (self._metrics.average_insert_ms * (self._metrics.total_inserts - 1) +
             (time.time() - t0) * 1000) / self._metrics.total_inserts
        )
        await self._publish(CacheStore(
            level=level.value, key=key.to_dict(),
            size=size, ttl_seconds=effective_ttl,
        ))

    def _evict_one(self, store: OrderedDict, level: CacheLevel) -> bool:
        # Pass 1: Try to evict non-pinned, non-priority entry (LRU)
        for key_str, entry in store.items():
            if entry.pinned or entry.priority:
                continue
            self._metrics.memory_usage = max(0, self._metrics.memory_usage - entry.size)
            del store[key_str]
            self._metrics.evictions += 1
            pl = self._metrics.per_level[level.value]
            pl["evictions"] += 1
            pl["entries"] = len(store)
            return True

        # Pass 2: Fallback to evicting non-pinned priority entry (LRU)
        for key_str, entry in store.items():
            if entry.pinned:
                continue
            self._metrics.memory_usage = max(0, self._metrics.memory_usage - entry.size)
            del store[key_str]
            self._metrics.evictions += 1
            pl = self._metrics.per_level[level.value]
            pl["evictions"] += 1
            pl["entries"] = len(store)
            return True

        return False

    async def invalidate(self, pattern: Optional[Dict[str, str]] = None,
                         level: Optional[CacheLevel] = None) -> int:
        removed = 0
        levels = [level] if level else CACHE_LEVELS_LIST

        for lv in levels:
            store = self._stores[lv]
            to_delete = []
            for key_str, entry in store.items():
                if entry.pinned:
                    continue
                if pattern is None:
                    to_delete.append(key_str)
                else:
                    if self._matches_pattern(entry.key, pattern):
                        to_delete.append(key_str)

            for key_str in to_delete:
                entry = store.pop(key_str)
                self._metrics.memory_usage = max(0, self._metrics.memory_usage - entry.size)
                if entry.pinned:
                    self._metrics.pinned_entries = max(0, self._metrics.pinned_entries - 1)
                removed += 1

            pl = self._metrics.per_level[lv.value]
            pl["entries"] = len(store)

        self._metrics.invalidations += removed
        if removed > 0:
            reason = f"pattern={pattern}" if pattern else "full"
            await self._publish(CacheInvalidate(
                level=level.value if level else "all",
                reason=reason, entries_removed=removed,
            ))
        return removed

    async def invalidate_level(self, level: CacheLevel) -> int:
        return await self.invalidate(level=level)

    def _matches_pattern(self, key: CacheKey, pattern: Dict[str, str]) -> bool:
        key_dict = key.to_dict()
        for k, v in pattern.items():
            if k in key_dict and key_dict[k] != v:
                return False
        return True

    async def clear(self) -> None:
        total = 0
        for level in CACHE_LEVELS_LIST:
            store = self._stores[level]
            total += len(store)
            for entry in store.values():
                self._metrics.memory_usage = max(0, self._metrics.memory_usage - entry.size)
            store.clear()
            pl = self._metrics.per_level[level.value]
            pl["entries"] = 0
        self._metrics.pinned_entries = 0
        await self._publish(CacheInvalidate(
            level="all", reason="clear", entries_removed=total,
        ))

    async def cleanup(self) -> int:
        removed = 0
        for level in CACHE_LEVELS_LIST:
            store = self._stores[level]
            to_delete = []
            for key_str, entry in store.items():
                if entry.expired:
                    to_delete.append(key_str)

            for key_str in to_delete:
                entry = store.pop(key_str)
                self._metrics.memory_usage = max(0, self._metrics.memory_usage - entry.size)
                removed += 1

            pl = self._metrics.per_level[level.value]
            pl["entries"] = len(store)

        if removed > 0:
            self._metrics.expirations += removed
            await self._publish(CacheExpired(level="all", entries_removed=removed))
            logger.debug(f"Cache cleanup removed {removed} expired entries.")
        return removed

    async def _background_cleanup(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                removed = await self.cleanup()
                if removed > 0:
                    await self._publish(CacheExpired(
                        level="all", entries_removed=removed,
                    ))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Cache cleanup error: {e}")

    def metrics(self) -> CacheMetrics:
        total_entries = sum(len(s) for s in self._stores.values())
        self._metrics.entries_count = total_entries
        return self._metrics

    def get_entry_count(self, level: Optional[CacheLevel] = None) -> int:
        if level:
            return len(self._stores[level])
        return sum(len(s) for s in self._stores.values())

    def _estimate_size(self, value: Any) -> int:
        try:
            raw = json.dumps(value, default=str)
            return len(raw)
        except Exception:
            return len(str(value))

    async def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                await self._event_bus.publish(event)
            except Exception:
                pass

    def _invalidate_for_session(self, session_id: str) -> None:
        asyncio.ensure_future(self.invalidate({"session_id": session_id}))

    def _invalidate_for_level(self, level: CacheLevel) -> None:
        asyncio.ensure_future(self.invalidate(level=level))

    async def invalidate_with_dependencies(self, level: CacheLevel, reason: str = "", session_id: Optional[str] = None) -> int:
        levels_to_invalidate = [level]
        if level in (CacheLevel.CONVERSATION, CacheLevel.MEMORY, CacheLevel.KNOWLEDGE,
                     CacheLevel.WORKFLOW, CacheLevel.DESKTOP, CacheLevel.MISSION, CacheLevel.TOOL_RESULTS):
            levels_to_invalidate.append(CacheLevel.RANKING_RESULTS)
            levels_to_invalidate.append(CacheLevel.COMPRESSED_CONTEXT)
        elif level == CacheLevel.RANKING_RESULTS:
            levels_to_invalidate.append(CacheLevel.COMPRESSED_CONTEXT)

        removed = 0
        pattern = {"session_id": session_id} if session_id else None
        for lv in levels_to_invalidate:
            removed += await self.invalidate(pattern=pattern, level=lv)
        return removed

    def _subscribe_to_events(self) -> None:
        if not self._event_bus:
            return

        # Memory events
        for topic in ["MemoryCreated", "MemoryUpdated", "MemoryExpired", "ProjectUpdated", "UserPreferenceChanged"]:
            self._event_bus.subscribe(topic, self._on_memory_changed)

        # Desktop events
        for topic in ["DesktopChanged", "WindowOpened", "WindowClosed", "desktop.*"]:
            self._event_bus.subscribe(topic, self._on_desktop_changed)

        # Workflow events
        for topic in ["WorkflowStarted", "WorkflowPaused", "WorkflowResumed", "WorkflowStepCompleted", "WorkflowFailed", "WorkflowCompleted", "WorkflowCancelled"]:
            self._event_bus.subscribe(topic, self._on_workflow_changed)

        # Tool events
        for topic in ["ToolExecuted", "ToolFailed", "ToolCompleted", "ToolOutputChanged"]:
            self._event_bus.subscribe(topic, self._on_tool_output_changed)

        # Knowledge events
        for topic in ["DocumentIndexed", "DocumentUpdated", "DocumentDeleted"]:
            self._event_bus.subscribe(topic, self._on_knowledge_updated)

        # Conversation reset events
        for topic in ["ConversationReset", "ConversationCleared", "ConversationCompleted"]:
            self._event_bus.subscribe(topic, self._on_conversation_reset)

        # Model change events
        for topic in ["ModelChanged", "model_changed"]:
            self._event_bus.subscribe(topic, self._on_model_changed)

        # Strategy change events
        for topic in ["StrategyResolved", "StrategyChanged"]:
            self._event_bus.subscribe(topic, self._on_strategy_changed)

    def _unsubscribe_from_events(self) -> None:
        if not self._event_bus:
            return

        # Memory events
        for topic in ["MemoryCreated", "MemoryUpdated", "MemoryExpired", "ProjectUpdated", "UserPreferenceChanged"]:
            self._event_bus.unsubscribe(topic, self._on_memory_changed)

        # Desktop events
        for topic in ["DesktopChanged", "WindowOpened", "WindowClosed", "desktop.*"]:
            self._event_bus.unsubscribe(topic, self._on_desktop_changed)

        # Workflow events
        for topic in ["WorkflowStarted", "WorkflowPaused", "WorkflowResumed", "WorkflowStepCompleted", "WorkflowFailed", "WorkflowCompleted", "WorkflowCancelled"]:
            self._event_bus.unsubscribe(topic, self._on_workflow_changed)

        # Tool events
        for topic in ["ToolExecuted", "ToolFailed", "ToolCompleted", "ToolOutputChanged"]:
            self._event_bus.unsubscribe(topic, self._on_tool_output_changed)

        # Knowledge events
        for topic in ["DocumentIndexed", "DocumentUpdated", "DocumentDeleted"]:
            self._event_bus.unsubscribe(topic, self._on_knowledge_updated)

        # Conversation reset events
        for topic in ["ConversationReset", "ConversationCleared", "ConversationCompleted"]:
            self._event_bus.unsubscribe(topic, self._on_conversation_reset)

        # Model change events
        for topic in ["ModelChanged", "model_changed"]:
            self._event_bus.unsubscribe(topic, self._on_model_changed)

        # Strategy change events
        for topic in ["StrategyResolved", "StrategyChanged"]:
            self._event_bus.unsubscribe(topic, self._on_strategy_changed)

    async def _on_memory_changed(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_memory_change:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.MEMORY, reason=f"Memory change ({event.topic})", session_id=session_id)

    async def _on_desktop_changed(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_desktop_change:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.DESKTOP, reason=f"Desktop change ({event.topic})", session_id=session_id)

    async def _on_workflow_changed(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_workflow_change:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.WORKFLOW, reason=f"Workflow change ({event.topic})", session_id=session_id)

    async def _on_tool_output_changed(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_tool_output_change:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.TOOL_RESULTS, reason=f"Tool output change ({event.topic})", session_id=session_id)

    async def _on_knowledge_updated(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_knowledge_update:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.KNOWLEDGE, reason=f"Knowledge update ({event.topic})", session_id=session_id)

    async def _on_conversation_reset(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_conversation_reset:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.CONVERSATION, reason=f"Conversation reset ({event.topic})", session_id=session_id)

    async def _on_model_changed(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_model_change:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.RANKING_RESULTS, reason=f"Model change ({event.topic})", session_id=session_id)
            await self.invalidate_with_dependencies(CacheLevel.COMPRESSED_CONTEXT, reason=f"Model change ({event.topic})", session_id=session_id)

    async def _on_strategy_changed(self, event: FridayEvent) -> None:
        if self._invalidation_policy.on_strategy_change:
            session_id = event.data.get("session_id")
            await self.invalidate_with_dependencies(CacheLevel.RANKING_RESULTS, reason=f"Strategy change ({event.topic})", session_id=session_id)
            await self.invalidate_with_dependencies(CacheLevel.COMPRESSED_CONTEXT, reason=f"Strategy change ({event.topic})", session_id=session_id)
