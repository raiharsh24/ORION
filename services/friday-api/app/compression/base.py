from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from app.budget.base import AllocatedBlock
from app.context.base import StrategyConfig
from app.validation.base import ValidationReport
from app.budget.base import BudgetReport


class CompressionPolicy(str, Enum):
    NONE = "none"
    LIGHT = "light"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"


@dataclass
class CompressedBlock:
    block: AllocatedBlock
    original_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 0.0
    estimated_savings: int = 0
    policy_applied: str = "none"

    def __post_init__(self):
        if self.original_tokens > 0:
            self.compression_ratio = round(
                1.0 - (self.compressed_tokens / self.original_tokens), 4
            )
        self.estimated_savings = self.original_tokens - self.compressed_tokens


@dataclass
class CompressionReport:
    input_tokens: int = 0
    output_tokens: int = 0
    saved_tokens: int = 0
    compression_ratio: float = 0.0
    per_block_statistics: List[Dict[str, object]] = field(default_factory=list)
    skipped_blocks: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class CompressionResult:
    compressed_blocks: List[CompressedBlock] = field(default_factory=list)
    report: Optional[CompressionReport] = None

    @property
    def total_original_tokens(self) -> int:
        return sum(cb.original_tokens for cb in self.compressed_blocks)

    @property
    def total_compressed_tokens(self) -> int:
        return sum(cb.compressed_tokens for cb in self.compressed_blocks)


DEFAULT_COMPRESSION_POLICY = CompressionPolicy.STANDARD


class IContextCompressor(ABC):

    @property
    @abstractmethod
    def compressor_name(self) -> str:
        ...

    @abstractmethod
    def compress(
        self,
        blocks: List[AllocatedBlock],
        policy: CompressionPolicy = DEFAULT_COMPRESSION_POLICY,
        strategy: Optional[StrategyConfig] = None,
    ) -> CompressionResult:
        ...
