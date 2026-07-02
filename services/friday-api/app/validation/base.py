from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.budget.base import AllocatedBlock
from app.context.base import StrategyConfig


SUPPORTED_SOURCE_PREFIXES: Set[str] = {
    "memory", "knowledge", "workflow", "desktop", "browser",
    "terminal", "mission", "voice", "system", "web", "project",
}


@dataclass
class ValidationConfig:
    max_metadata_size: int = 5_000
    max_source_length: int = 100
    allowed_source_prefixes: Set[str] = field(default_factory=lambda: SUPPORTED_SOURCE_PREFIXES)
    enable_conflict_detection: bool = True
    enable_duplicate_content_detection: bool = True
    enable_content_empty_check: bool = True


DEFAULT_VALIDATION_CONFIG = ValidationConfig()


@dataclass
class ValidationReport:
    input_blocks: int = 0
    valid_blocks: int = 0
    removed_duplicates: int = 0
    removed_invalid: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        return self.removed_duplicates + self.removed_invalid


@dataclass
class ValidationResult:
    valid_blocks: List[AllocatedBlock] = field(default_factory=list)
    report: Optional[ValidationReport] = None


class IContextValidator(ABC):

    @property
    @abstractmethod
    def validator_name(self) -> str:
        ...

    @abstractmethod
    def validate(
        self,
        blocks: List[AllocatedBlock],
        config: Optional[ValidationConfig] = None,
        strategy: Optional[StrategyConfig] = None,
    ) -> ValidationResult:
        ...
