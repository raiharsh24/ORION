import time
import asyncio
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from app.memory.schema import MemoryEntry, SessionMemory
from app.memory.store import MemoryStore
from app.memory.manager import MemoryManager
from app.memory.serializer import MemorySerializer
from app.memory.events import (
    MemoryCreated, MemoryUpdated, MemoryError, SessionSummarized,
)


class MemoryConsolidator:
    """Background memory consolidator that summarizes conversations,
    extracts facts/preferences/patterns, and discards low-value context.

    Runs periodically or on-demand to compress episodic memory into
    semantic knowledge.
    """

    def __init__(
        self,
        manager: MemoryManager,
        llm_router: Optional[Any] = None,
        min_importance_threshold: int = 3,
        max_session_age_days: int = 7,
    ) -> None:
        self._manager = manager
        self._llm_router = llm_router
        self._min_importance = min_importance_threshold
        self._max_session_age = max_session_age_days * 86400
        self._running = False
        self._task: Optional[asyncio.Task] = None

        self.sessions_summarized = 0
        self.facts_extracted = 0
        self.preferences_detected = 0
        self.entries_discarded = 0
        self.total_runs = 0

    async def start(self, interval_seconds: int = 3600) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(interval_seconds))
        logger.info(f"MemoryConsolidator started (interval={interval_seconds}s)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("MemoryConsolidator stopped")

    async def _run_loop(self, interval: int) -> None:
        while self._running:
            try:
                await self.run_consolidation()
            except Exception as e:
                logger.error(f"MemoryConsolidation run failed: {e}")
            await asyncio.sleep(interval)

    async def run_consolidation(self) -> Dict[str, Any]:
        self.total_runs += 1
        start = time.time()

        sessions = await self._consolidate_sessions()
        facts = await self._extract_facts()
        prefs = await self._detect_preferences()
        discarded = await self._discard_low_value()

        elapsed = (time.time() - start) * 1000
        stats = {
            "sessions_summarized": sessions,
            "facts_extracted": facts,
            "preferences_detected": prefs,
            "entries_discarded": discarded,
            "duration_ms": round(elapsed, 2),
        }
        logger.info(f"MemoryConsolidation completed: {stats}")
        return stats

    async def _consolidate_sessions(self) -> int:
        count = 0
        now = time.time()
        for key in self._manager._store.keys():
            if not key.startswith("session:"):
                continue
            data = self._manager._store.get(key)
            if not data:
                continue
            try:
                session = MemorySerializer.deserialize_session(data)
            except Exception:
                continue

            if len(session.messages) < 4:
                continue

            if session.summary and "Summary:" in session.summary:
                continue

            summary = self._generate_summary(session)
            if summary:
                session.summary = summary
                self._manager.save_session(session)
                self._manager._safe_publish(SessionSummarized(
                    session_id=session.session_id, summary=summary
                ))
                count += 1

        self.sessions_summarized += count
        return count

    async def _extract_facts(self) -> int:
        count = 0
        for key in self._manager._store.keys():
            if not key.startswith("session:"):
                continue
            data = self._manager._store.get(key)
            if not data:
                continue
            try:
                session = MemorySerializer.deserialize_session(data)
            except Exception:
                continue

            if not session.summary or "Summary:" in session.summary:
                continue

            fact_entry = MemoryEntry(
                content=f"Session summary: {session.summary}",
                category="general",
                importance=6,
                metadata={
                    "source": "consolidation",
                    "session_id": session.session_id,
                    "message_count": len(session.messages),
                },
            )
            self._manager._store.put(
                f"consolidated:fact:{session.session_id}",
                MemorySerializer.serialize_entry(fact_entry),
            )
            count += 1

        self.facts_extracted += count
        return count

    async def _detect_preferences(self) -> int:
        count = 0
        preference_keywords = ["prefer", "like", "want", "would like", "please use", "always", "never"]

        for key in self._manager._store.keys():
            if not key.startswith("session:"):
                continue
            data = self._manager._store.get(key)
            if not data:
                continue
            try:
                session = MemorySerializer.deserialize_session(data)
            except Exception:
                continue

            user_id = session.metadata.get("user_id", "default_user") if session.metadata else "default_user"

            for msg in session.messages:
                if msg.role != "user":
                    continue
                content_lower = msg.content.lower()
                for kw in preference_keywords:
                    if kw in content_lower:
                        pref_entry = MemoryEntry(
                            content=f"User preference detected: {msg.content[:200]}",
                            category="preference",
                            importance=7,
                            metadata={
                                "source": "consolidation",
                                "session_id": session.session_id,
                                "user_id": user_id,
                                "keyword": kw,
                            },
                        )
                        self._manager._store.put(
                            f"consolidated:preference:{session.session_id}:{int(time.time())}",
                            MemorySerializer.serialize_entry(pref_entry),
                        )
                        count += 1
                        break

        self.preferences_detected += count
        return count

    async def _discard_low_value(self) -> int:
        count = 0
        now = time.time()

        for key in list(self._manager._store.keys()):
            if key.startswith("session:"):
                data = self._manager._store.get(key)
                if not data:
                    continue
                try:
                    session = MemorySerializer.deserialize_session(data)
                except Exception:
                    continue

                age = now - session.updated_at
                if age > self._max_session_age and not session.summary:
                    messages_kept = 0
                    for msg in list(session.messages):
                        msg_age = now - msg.timestamp
                        if msg_age > self._max_session_age:
                            session.messages.remove(msg)
                            count += 1
                            messages_kept += 1

                    if len(session.messages) > 200:
                        session.messages = session.messages[-200:]
                        count += 1

                    session.summary = self._generate_summary(session) or session.summary
                    self._manager.save_session(session)

        self.entries_discarded += count
        return count

    def _generate_summary(self, session: SessionMemory) -> Optional[str]:
        msg_count = len(session.messages)
        if msg_count == 0:
            return None

        user_msgs = sum(1 for m in session.messages if m.role == "user")
        asst_msgs = sum(1 for m in session.messages if m.role == "assistant")
        tool_msgs = sum(1 for m in session.messages if m.role == "system")

        last_user_msg = ""
        for m in reversed(session.messages):
            if m.role == "user":
                last_user_msg = m.content[:100]
                break

        return (
            f"Summary: {msg_count} messages "
            f"({user_msgs} user, {asst_msgs} assistant, {tool_msgs} system). "
            f"Last user topic: {last_user_msg}."
        )

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY" if self._running else "STOPPED",
            "details": {
                "running": self._running,
                "total_runs": self.total_runs,
                "sessions_summarized": self.sessions_summarized,
                "facts_extracted": self.facts_extracted,
                "preferences_detected": self.preferences_detected,
                "entries_discarded": self.entries_discarded,
            },
        }
