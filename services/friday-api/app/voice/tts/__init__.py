import asyncio
from abc import ABC, abstractmethod
from typing import Dict, AsyncIterator, Optional, List

class BaseTTSProvider(ABC):
    """
    Abstract interface for all Text-to-Speech engines.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """
        Synthesizes text input into a stream of raw audio bytes.
        """
        # Yield dummy value to satisfy abstractmethod syntax structure
        yield b""

class TTSProviderRegistry:
    """
    Registry for managing and resolving dynamic TTS Providers.
    """
    def __init__(self) -> None:
        self._providers: Dict[str, BaseTTSProvider] = {}
        self._default_provider: Optional[str] = None

    def register(self, provider: BaseTTSProvider, is_default: bool = False) -> None:
        self._providers[provider.name] = provider
        if is_default or not self._default_provider:
            self._default_provider = provider.name

    def get(self, name: Optional[str] = None) -> Optional[BaseTTSProvider]:
        provider_name = name or self._default_provider
        return self._providers.get(provider_name) if provider_name else None

    @property
    def default_provider_name(self) -> Optional[str]:
        return self._default_provider

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

class MockTTSProvider(BaseTTSProvider):
    """
    Mock TTS engine for testing and architectural scaffolding.
    """
    @property
    def name(self) -> str:
        return "mock_tts"

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        yield f"AUDIO:{text}".encode()

class TTSCoordinator:
    """
    Orchestration coordinator directing text tokenization, sentence chunking,
    and provider streams resolution.
    """
    def __init__(self, registry: TTSProviderRegistry) -> None:
        self.registry = registry

    async def synthesize_stream(self, text: str, provider_name: Optional[str] = None) -> AsyncIterator[bytes]:
        provider = self.registry.get(provider_name)
        if not provider:
            raise ValueError(f"No TTS provider found (requested: {provider_name})")

        # Sentence-based tokenization scaffolding
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if not sentences and text.strip():
            sentences = [text.strip()]

        for sentence in sentences:
            async for chunk in provider.synthesize(sentence):
                yield chunk
