from app.events.events import FridayEvent
from typing import Dict, Any

class MemoryCreated(FridayEvent):
    def __init__(self, memory_id: str, category: str, data: Dict[str, Any]) -> None:
        payload = {"memory_id": memory_id, "category": category, "entry": data}
        super().__init__(topic="MemoryCreated", data=payload)

class MemoryUpdated(FridayEvent):
    def __init__(self, memory_id: str, category: str, data: Dict[str, Any]) -> None:
        payload = {"memory_id": memory_id, "category": category, "entry": data}
        super().__init__(topic="MemoryUpdated", data=payload)

class MemoryRetrieved(FridayEvent):
    def __init__(self, session_id: str, query: str, results_count: int) -> None:
        payload = {"session_id": session_id, "query": query, "results_count": results_count}
        super().__init__(topic="MemoryRetrieved", data=payload)

class MemoryExpired(FridayEvent):
    def __init__(self, memory_id: str, category: str) -> None:
        payload = {"memory_id": memory_id, "category": category}
        super().__init__(topic="MemoryExpired", data=payload)

class SessionSummarized(FridayEvent):
    def __init__(self, session_id: str, summary: str) -> None:
        payload = {"session_id": session_id, "summary": summary}
        super().__init__(topic="SessionSummarized", data=payload)

class ProjectUpdated(FridayEvent):
    def __init__(self, project_id: str, data: Dict[str, Any]) -> None:
        payload = {"project_id": project_id, "project": data}
        super().__init__(topic="ProjectUpdated", data=payload)

class UserPreferenceChanged(FridayEvent):
    def __init__(self, user_id: str, preferences: Dict[str, Any]) -> None:
        payload = {"user_id": user_id, "preferences": preferences}
        super().__init__(topic="UserPreferenceChanged", data=payload)

class MemoryError(FridayEvent):
    def __init__(self, action: str, message: str) -> None:
        payload = {"action": action, "message": message}
        super().__init__(topic="MemoryError", data=payload)

class MemoryCleanupCompleted(FridayEvent):
    def __init__(self, expired: int = 0, truncated: int = 0,
                 consolidated: int = 0, deduped: int = 0) -> None:
        payload = {
            "expired": expired,
            "truncated": truncated,
            "consolidated": consolidated,
            "deduped": deduped,
        }
        super().__init__(topic="MemoryCleanupCompleted", data=payload)

class LearningPatternStored(FridayEvent):
    def __init__(self, pattern_id: str, learning_type: str) -> None:
        payload = {"pattern_id": pattern_id, "learning_type": learning_type}
        super().__init__(topic="LearningPatternStored", data=payload)

class EpisodicRecorded(FridayEvent):
    def __init__(self, episodic_type: str, entry_id: str) -> None:
        payload = {"episodic_type": episodic_type, "entry_id": entry_id}
        super().__init__(topic="EpisodicRecorded", data=payload)

class GraphEntityCreated(FridayEvent):
    def __init__(self, entity_id: str, entity_type: str, name: str) -> None:
        payload = {"entity_id": entity_id, "entity_type": entity_type, "name": name}
        super().__init__(topic="GraphEntityCreated", data=payload)

class GraphRelationCreated(FridayEvent):
    def __init__(self, source_id: str, target_id: str, relation_type: str) -> None:
        payload = {"source_id": source_id, "target_id": target_id, "relation_type": relation_type}
        super().__init__(topic="GraphRelationCreated", data=payload)
