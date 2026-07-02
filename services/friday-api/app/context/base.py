from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from app.intent.types import IntentType


@dataclass
class TokenBudget:
    total: int = 4096
    system: int = 512
    conversation_history: int = 1024
    working_memory: int = 512
    retrieved_context: int = 1024
    instructions: int = 512
    reserved: int = 512


@dataclass
class RetrievalPriority:
    sources: List[str] = field(default_factory=lambda: [
        "working_memory",
        "project_memory",
        "user_preferences",
        "session_history",
        "knowledge_base",
    ])


@dataclass
class CompressionPolicy:
    strategy: str = "summarize"
    max_tokens: int = 2048
    threshold: float = 0.8


@dataclass
class CachePolicy:
    ttl_seconds: int = 120
    max_entries: int = 100
    invalidation: str = "lru"


@dataclass
class StrategyConfig:
    extractors: List[str] = field(default_factory=list)
    token_budget: TokenBudget = field(default_factory=TokenBudget)
    retrieval_priority: RetrievalPriority = field(default_factory=RetrievalPriority)
    compression_policy: CompressionPolicy = field(default_factory=CompressionPolicy)
    cache_policy: CachePolicy = field(default_factory=CachePolicy)


class ContextStrategy(ABC):
    @property
    @abstractmethod
    def intent_type(self) -> IntentType:
        ...

    @abstractmethod
    def get_config(self) -> StrategyConfig:
        ...
