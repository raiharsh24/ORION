from app.memory.engine import MemoryEngine
from app.memory.conversation import ChatMessage
from app.memory.embeddings import EmbeddingsManager
from app.memory.episodic import EpisodicMemory
from app.memory.graph import KnowledgeGraph, Entity, Relation
from app.memory.learning import LearningEngine
from app.memory.consolidator import MemoryConsolidator
from app.memory.manager import MemoryManager
from app.memory.retriever import MemoryRetriever
from app.memory.semantic import SemanticMemoryStore
from app.memory.store import MemoryStore, InMemoryStore, JSONStore, SQLiteStore
from app.memory.schema import MemoryEntry, SessionMemory, UserMemory, ProjectMemory, WorkingMemory

# Alias ConversationMemory to MemoryEngine for backward compatibility
ConversationMemory = MemoryEngine

__all__ = [
    "MemoryEngine",
    "ConversationMemory",
    "ChatMessage",
    "EmbeddingsManager",
    "EpisodicMemory",
    "KnowledgeGraph",
    "Entity",
    "Relation",
    "LearningEngine",
    "MemoryConsolidator",
    "MemoryManager",
    "MemoryRetriever",
    "SemanticMemoryStore",
    "MemoryStore",
    "InMemoryStore",
    "JSONStore",
    "SQLiteStore",
    "MemoryEntry",
    "SessionMemory",
    "UserMemory",
    "ProjectMemory",
    "WorkingMemory",
]
