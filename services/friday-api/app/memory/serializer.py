from typing import Dict, Any
from app.memory.schema import MemoryEntry, SessionMemory, UserMemory, ProjectMemory

class MemorySerializer:
    """
    Handles serialization and validation mapping for Memory layer models.
    """
    @staticmethod
    def serialize_entry(entry: MemoryEntry) -> Dict[str, Any]:
        return entry.model_dump()

    @staticmethod
    def deserialize_entry(data: Dict[str, Any]) -> MemoryEntry:
        return MemoryEntry.model_validate(data)

    @staticmethod
    def serialize_session(session: SessionMemory) -> Dict[str, Any]:
        return session.model_dump()

    @staticmethod
    def deserialize_session(data: Dict[str, Any]) -> SessionMemory:
        return SessionMemory.model_validate(data)

    @staticmethod
    def serialize_user(user: UserMemory) -> Dict[str, Any]:
        return user.model_dump()

    @staticmethod
    def deserialize_user(data: Dict[str, Any]) -> UserMemory:
        return UserMemory.model_validate(data)

    @staticmethod
    def serialize_project(project: ProjectMemory) -> Dict[str, Any]:
        return project.model_dump()

    @staticmethod
    def deserialize_project(data: Dict[str, Any]) -> ProjectMemory:
        return ProjectMemory.model_validate(data)
