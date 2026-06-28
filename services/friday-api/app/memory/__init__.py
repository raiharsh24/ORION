from app.memory.engine import MemoryEngine
from app.memory.conversation import ChatMessage
from app.memory.embeddings import EmbeddingsManager

# Alias ConversationMemory to MemoryEngine for backward compatibility
ConversationMemory = MemoryEngine

__all__ = [
    "MemoryEngine",
    "ConversationMemory",
    "ChatMessage",
    "EmbeddingsManager"
]
