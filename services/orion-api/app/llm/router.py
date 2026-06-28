from typing import Dict
from app.llm.base import BaseLLM
from loguru import logger

class LLMRouter:
    """
    Decouples model providers (Gemini, OpenAI, Claude, etc.) from the core ORION logic.
    """
    def __init__(self) -> None:
        self._providers: Dict[str, BaseLLM] = {}
        self._default_provider: str | None = None

    def register_provider(self, name: str, provider: BaseLLM, is_default: bool = False) -> None:
        logger.info(f"Registering LLM provider: '{name}'")
        self._providers[name] = provider
        if is_default or not self._default_provider:
            self._default_provider = name

    def get_provider(self, name: str | None = None) -> BaseLLM:
        target = name or self._default_provider
        if not target:
            raise ValueError("No LLM providers registered in LLMRouter.")
        
        provider = self._providers.get(target)
        if not provider:
            raise ValueError(f"LLM provider '{target}' is not registered.")
        
        return provider

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())
