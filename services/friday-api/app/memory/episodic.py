import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.memory.schema import MemoryEntry
from app.memory.store import MemoryStore, InMemoryStore
from app.memory.serializer import MemorySerializer


class EpisodicMemory:
    """Explicit episodic memory layer for mission/tool/workflow history.

    Hierarchy: WorkingMemory (request) → SessionMemory (conversation)
    → EpisodicMemory (past missions/tools) → SemanticMemory (facts/concepts)
    → LongTermKnowledge (documents/embeddings).
    """

    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self._store = store or InMemoryStore()

    def _key(self, type_: str, id_: str) -> str:
        return f"episodic:{type_}:{id_}"

    def record_mission(
        self,
        mission_id: str,
        name: str,
        description: str,
        status: str,
        priority: str = "medium",
        duration_ms: float = 0.0,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            content=f"Mission '{name}': {description}",
            category="episodic",
            importance=7 if status == "completed" else 8 if error else 6,
            metadata={
                "episodic_type": "mission",
                "mission_id": mission_id,
                "mission_name": name,
                "status": status,
                "priority": priority,
                "duration_ms": duration_ms,
                "error": error,
                **(metadata or {}),
            },
        )
        self._store.put(self._key("mission", mission_id), MemorySerializer.serialize_entry(entry))
        return entry

    def record_tool_use(
        self,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        success: bool,
        duration_ms: float = 0.0,
        session_id: str = "global",
        mission_id: Optional[str] = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            content=f"Tool '{tool_name}': {input_summary}",
            category="episodic",
            importance=5,
            metadata={
                "episodic_type": "tool",
                "tool_name": tool_name,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "success": success,
                "duration_ms": duration_ms,
                "session_id": session_id,
                "mission_id": mission_id,
            },
        )
        tool_key = f"{tool_name}:{int(time.time())}"
        self._store.put(self._key("tool", tool_key), MemorySerializer.serialize_entry(entry))
        return entry

    def record_workflow(
        self,
        workflow_id: str,
        name: str,
        status: str,
        steps_count: int = 0,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            content=f"Workflow '{name}' ({workflow_id})",
            category="episodic",
            importance=6,
            metadata={
                "episodic_type": "workflow",
                "workflow_id": workflow_id,
                "workflow_name": name,
                "status": status,
                "steps_count": steps_count,
                "duration_ms": duration_ms,
                "error": error,
            },
        )
        self._store.put(self._key("workflow", workflow_id), MemorySerializer.serialize_entry(entry))
        return entry

    def query_recent(self, limit: int = 10) -> List[MemoryEntry]:
        all_entries: List[MemoryEntry] = []
        for key in self._store.keys():
            if key.startswith("episodic:"):
                data = self._store.get(key)
                if data:
                    all_entries.append(MemorySerializer.deserialize_entry(data))
        all_entries.sort(key=lambda e: e.timestamp, reverse=True)
        return all_entries[:limit]

    def query_by_type(self, type_: str, limit: int = 10) -> List[MemoryEntry]:
        prefix = f"episodic:{type_}:"
        entries: List[MemoryEntry] = []
        for key in self._store.keys():
            if key.startswith(prefix):
                data = self._store.get(key)
                if data:
                    entries.append(MemorySerializer.deserialize_entry(data))
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def get_mission(self, mission_id: str) -> Optional[MemoryEntry]:
        data = self._store.get(self._key("mission", mission_id))
        if data:
            return MemorySerializer.deserialize_entry(data)
        return None

    def clear(self) -> None:
        for key in list(self._store.keys()):
            if key.startswith("episodic:"):
                self._store.delete(key)
