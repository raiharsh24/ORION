from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


@dataclass
class ContextBlock:
    source: str = ""
    title: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 1.0
    importance: float = 0.5
    estimated_tokens: int = 0


@dataclass
class ExtractionResult:
    blocks: List[ContextBlock] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.blocks)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def total_estimated_tokens(self) -> int:
        return sum(b.estimated_tokens for b in self.blocks)


class IContextExtractor(ABC):
    @property
    @abstractmethod
    def extractor_name(self) -> str:
        ...

    @property
    def aliases(self) -> List[str]:
        return [self.extractor_name]

    @property
    @abstractmethod
    def supported_sources(self) -> List[str]:
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        ...

    @abstractmethod
    async def extract(self, request: str) -> List[ContextBlock]:
        ...
