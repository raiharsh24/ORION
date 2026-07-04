from typing import Dict, List, Optional
from loguru import logger

from app.vision.base import BaseVisionProvider


class VisionRouter:
    def __init__(self) -> None:
        self._providers: Dict[str, BaseVisionProvider] = {}
        self._default: Optional[str] = None

    def register_provider(self, name: str, provider: BaseVisionProvider, is_default: bool = False) -> None:
        self._providers[name] = provider
        if is_default or self._default is None:
            self._default = name
        logger.info(f"VisionRouter: registered provider '{name}' (default={is_default})")

    def get_provider(self, name: Optional[str] = None) -> BaseVisionProvider:
        provider_name = name or self._default
        if not provider_name:
            raise ValueError("No vision provider registered and no default set")
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Vision provider '{provider_name}' not found. Available: {list(self._providers.keys())}")
        return provider

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def health(self) -> dict:
        return {
            "status": "HEALTHY",
            "default_provider": self._default,
            "registered_providers": len(self._providers),
        }

    async def analyze_image(self, image_data: bytes, prompt: Optional[str] = None, provider_name: Optional[str] = None) -> dict:
        provider = self.get_provider(provider_name)
        return await provider.analyze_image(image_data, prompt)

    async def ocr(self, image_data: bytes, provider_name: Optional[str] = None) -> str:
        provider = self.get_provider(provider_name)
        return await provider.ocr(image_data)

    async def detect_ui_elements(self, image_data: bytes, provider_name: Optional[str] = None) -> list:
        provider = self.get_provider(provider_name)
        return await provider.detect_ui_elements(image_data)
