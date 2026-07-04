import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.memory.schema import MemoryEntry
from app.memory.store import MemoryStore, InMemoryStore
from app.memory.serializer import MemorySerializer
from app.memory.events import MemoryCreated, MemoryUpdated
from app.events.events import FridayEvent


class LearningEngine:
    """Post-mission learning engine that extracts success patterns,
    failure reasons, tool effectiveness, and reflections.

    Stores learnings in memory with category 'learned_pattern' and
    loads relevant learnings before subsequent missions.
    """

    def __init__(self, store: Optional[MemoryStore] = None, event_bus: Optional[Any] = None) -> None:
        self._store = store or InMemoryStore()
        self._event_bus = event_bus

        # Telemetry
        self.patterns_stored = 0
        self.missions_analyzed = 0

    def _safe_publish(self, event: FridayEvent) -> None:
        if not self._event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self._event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    self._event_bus.publish_background(event)
                except RuntimeError:
                    asyncio.run(self._event_bus.publish(event))
            else:
                self._event_bus.publish(event)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")

    def _learning_key(self, pattern_id: str) -> str:
        return f"learning:pattern:{pattern_id}"

    def record_mission_outcome(
        self,
        mission_id: str,
        success: bool,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        stages_planned: int = 0,
        stages_completed: int = 0,
        pattern_summary: Optional[str] = None,
    ) -> str:
        self.missions_analyzed += 1
        pattern_id = f"{mission_id}:{int(time.time())}"

        if success:
            content = (
                pattern_summary
                or f"Success pattern: Mission {mission_id} completed "
                f"{stages_completed}/{stages_planned} stages in {duration_ms:.0f}ms"
            )
            importance = 8
        else:
            content = (
                pattern_summary
                or f"Failure pattern: Mission {mission_id} failed: {error or 'unknown'}"
            )
            importance = 9

        entry = MemoryEntry(
            content=content,
            category="learned_pattern",
            importance=importance,
            metadata={
                "learning_type": "mission_outcome",
                "mission_id": mission_id,
                "success": success,
                "error": error,
                "duration_ms": duration_ms,
                "stages_planned": stages_planned,
                "stages_completed": stages_completed,
                "source": "learning_engine",
            },
        )
        self._store.put(self._learning_key(pattern_id), MemorySerializer.serialize_entry(entry))
        self.patterns_stored += 1

        self._safe_publish(MemoryCreated(
            memory_id=pattern_id,
            category="learned_pattern",
            data=entry.model_dump(),
        ))
        return pattern_id

    def record_tool_effectiveness(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float = 0.0,
        input_context: str = "",
        mission_id: Optional[str] = None,
    ) -> str:
        pattern_id = f"tool:{tool_name}:{int(time.time())}"

        content = (
            f"Tool '{tool_name}' {'succeeded' if success else 'failed'} "
            f"in {duration_ms:.0f}ms"
        )
        entry = MemoryEntry(
            content=content,
            category="learned_pattern",
            importance=6,
            metadata={
                "learning_type": "tool_effectiveness",
                "tool_name": tool_name,
                "success": success,
                "duration_ms": duration_ms,
                "input_context": input_context[:200],
                "mission_id": mission_id,
                "source": "learning_engine",
            },
        )
        self._store.put(self._learning_key(pattern_id), MemorySerializer.serialize_entry(entry))
        self.patterns_stored += 1
        return pattern_id

    def record_reflection(
        self,
        category: str,
        description: str,
        severity: str = "info",
        recommendation: str = "",
        mission_id: Optional[str] = None,
    ) -> str:
        pattern_id = f"reflection:{category}:{int(time.time())}"

        entry = MemoryEntry(
            content=description,
            category="learned_pattern",
            importance=7 if severity == "error" else 6 if severity == "warning" else 5,
            metadata={
                "learning_type": "reflection",
                "reflection_category": category,
                "severity": severity,
                "recommendation": recommendation,
                "mission_id": mission_id,
                "source": "learning_engine",
            },
        )
        self._store.put(self._learning_key(pattern_id), MemorySerializer.serialize_entry(entry))
        self.patterns_stored += 1
        return pattern_id

    def get_relevant_learnings(
        self,
        query: str = "",
        learning_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        entries: List[MemoryEntry] = []
        for key in self._store.keys():
            if not key.startswith("learning:pattern:"):
                continue
            data = self._store.get(key)
            if not data:
                continue
            try:
                entry = MemorySerializer.deserialize_entry(data)
            except Exception:
                continue

            if learning_type and entry.metadata.get("learning_type") != learning_type:
                continue

            if query:
                query_lower = query.lower()
                if (
                    query_lower in entry.content.lower()
                    or query_lower in str(entry.metadata).lower()
                ):
                    entries.append(entry)
            else:
                entries.append(entry)

        entries.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        return entries[:limit]

    def get_tool_effectiveness(
        self,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        entries = self.get_relevant_learnings(learning_type="tool_effectiveness")
        tool_stats: Dict[str, Dict[str, Any]] = {}

        for e in entries:
            meta = e.metadata
            tn = meta.get("tool_name", "unknown")
            if tool_name and tn != tool_name:
                continue

            if tn not in tool_stats:
                tool_stats[tn] = {"success": 0, "fail": 0, "total_duration": 0.0, "count": 0}

            if meta.get("success"):
                tool_stats[tn]["success"] += 1
            else:
                tool_stats[tn]["fail"] += 1
            tool_stats[tn]["total_duration"] += meta.get("duration_ms", 0)
            tool_stats[tn]["count"] += 1

        result = {}
        for tn, stats in tool_stats.items():
            total = stats["success"] + stats["fail"]
            result[tn] = {
                "success_count": stats["success"],
                "fail_count": stats["fail"],
                "success_rate": round(stats["success"] / total, 2) if total > 0 else 0.0,
                "avg_duration_ms": round(stats["total_duration"] / total, 1) if total > 0 else 0.0,
                "total_uses": total,
            }
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "patterns_stored": self.patterns_stored,
            "missions_analyzed": self.missions_analyzed,
        }

    def clear(self) -> None:
        for key in list(self._store.keys()):
            if key.startswith("learning:"):
                self._store.delete(key)
