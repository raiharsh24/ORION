from app.events.events import OrionEvent
from typing import Dict, Any

class MemoryCreated(OrionEvent):
    def __init__(self, memory_id: str, category: str, data: Dict[str, Any]) -> None:
        payload = {"memory_id": memory_id, "category": category, "entry": data}
        super().__init__(topic="MemoryCreated", data=payload)

class MemoryUpdated(OrionEvent):
    def __init__(self, memory_id: str, category: str, data: Dict[str, Any]) -> None:
        payload = {"memory_id": memory_id, "category": category, "entry": data}
        super().__init__(topic="MemoryUpdated", data=payload)

class MemoryRetrieved(OrionEvent):
    def __init__(self, session_id: str, query: str, results_count: int) -> None:
        payload = {"session_id": session_id, "query": query, "results_count": results_count}
        super().__init__(topic="MemoryRetrieved", data=payload)

class MemoryExpired(OrionEvent):
    def __init__(self, memory_id: str, category: str) -> None:
        payload = {"memory_id": memory_id, "category": category}
        super().__init__(topic="MemoryExpired", data=payload)

class SessionSummarized(OrionEvent):
    def __init__(self, session_id: str, summary: str) -> None:
        payload = {"session_id": session_id, "summary": summary}
        super().__init__(topic="SessionSummarized", data=payload)

class ProjectUpdated(OrionEvent):
    def __init__(self, project_id: str, data: Dict[str, Any]) -> None:
        payload = {"project_id": project_id, "project": data}
        super().__init__(topic="ProjectUpdated", data=payload)

class UserPreferenceChanged(OrionEvent):
    def __init__(self, user_id: str, preferences: Dict[str, Any]) -> None:
        payload = {"user_id": user_id, "preferences": preferences}
        super().__init__(topic="UserPreferenceChanged", data=payload)

class MemoryError(OrionEvent):
    def __init__(self, action: str, message: str) -> None:
        payload = {"action": action, "message": message}
        super().__init__(topic="MemoryError", data=payload)
