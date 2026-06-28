from abc import ABC, abstractmethod
from typing import List
from loguru import logger
from app.memory.embeddings import EmbeddingsManager

class EmbeddingProvider(ABC):
    """
    Abstract EmbeddingProvider interface.
    """
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        pass

class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Interchangeable provider delegating to Gemini generative AI.
    """
    def __init__(self) -> None:
        self._manager = EmbeddingsManager()

    async def embed_text(self, text: str) -> List[float]:
        return await self._manager.embed_text(text)

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Placeholder class for future OpenAI embedding provider extensions.
    """
    async def embed_text(self, text: str) -> List[float]:
        logger.info("OpenAIEmbeddingProvider mock query called.")
        # Fallback to standard 1536 dimension mock vector
        return [0.1] * 1536

class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Fallback local MD5 hash embedding provider.
    """
    def __init__(self) -> None:
        self._manager = EmbeddingsManager()

    async def embed_text(self, text: str) -> List[float]:
        # Reuse local md5 word hashing implementation
        return self._manager._get_mock_embedding(text)
