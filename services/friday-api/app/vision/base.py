from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseVisionProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def analyze_image(self, image_data: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def ocr(self, image_data: bytes) -> str:
        ...

    @abstractmethod
    async def detect_ui_elements(self, image_data: bytes) -> List[Dict[str, Any]]:
        ...

    def health(self) -> Dict[str, Any]:
        return {"status": "HEALTHY", "provider": self.name}
