from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.context.base import StrategyConfig
from app.ranking.base import RankedContextBlock


MODEL_LIMITS: Dict[str, Dict[str, int]] = {
    "gemini-2.0-flash": {"context_window": 1_048_576, "max_output": 8_192},
    "gemini-1.5-pro":   {"context_window": 1_048_576, "max_output": 8_192},
    "gemini-1.5-flash": {"context_window": 1_048_576, "max_output": 8_192},
    "gpt-4o":           {"context_window": 128_000,   "max_output": 16_384},
    "gpt-4-turbo":      {"context_window": 128_000,   "max_output": 4_096},
    "gpt-4":            {"context_window": 32_768,    "max_output": 4_096},
    "gpt-3.5-turbo":    {"context_window": 16_384,    "max_output": 4_096},
    "claude-3-opus":    {"context_window": 200_000,   "max_output": 4_096},
    "claude-3-sonnet":  {"context_window": 200_000,   "max_output": 4_096},
    "claude-3-haiku":   {"context_window": 200_000,   "max_output": 4_096},
}

DEFAULT_MODEL = "gemini-1.5-pro"
DEFAULT_CONTEXT_WINDOW = 128_000
DEFAULT_MAX_OUTPUT = 8_192


@dataclass
class BudgetConfig:
    model_name: str = DEFAULT_MODEL
    context_window: int = DEFAULT_CONTEXT_WINDOW
    reserved_response_tokens: int = 4_096
    system_prompt_reservation: int = 2_048
    conversation_history_reservation: int = 4_096
    min_guaranteed_per_block: int = 128
    max_per_block: int = 16_384

    @classmethod
    def for_model(cls, model_name: str, **overrides) -> "BudgetConfig":
        limits = MODEL_LIMITS.get(model_name, {})
        ctx = limits.get("context_window", DEFAULT_CONTEXT_WINDOW)
        max_out = limits.get("max_output", DEFAULT_MAX_OUTPUT)
        return cls(
            model_name=model_name,
            context_window=ctx,
            reserved_response_tokens=overrides.pop("reserved_response_tokens", max_out),
            **overrides,
        )


@dataclass
class BudgetReport:
    total_budget: int = 0
    reserved_tokens: int = 0
    allocated_tokens: int = 0
    discarded_tokens: int = 0
    utilization_percentage: float = 0.0
    selected_blocks: int = 0
    discarded_blocks: int = 0
    total_blocks_input: int = 0
    details: Dict[str, object] = field(default_factory=dict)

    @property
    def available_tokens(self) -> int:
        return self.total_budget - self.reserved_tokens


@dataclass
class AllocatedBlock:
    block: RankedContextBlock
    allocated_tokens: int = 0
    is_truncated: bool = False


@dataclass
class AllocationResult:
    selected_blocks: List[AllocatedBlock] = field(default_factory=list)
    discarded_blocks: List[RankedContextBlock] = field(default_factory=list)
    report: Optional[BudgetReport] = None

    @property
    def total_selected(self) -> int:
        return len(self.selected_blocks)

    @property
    def total_discarded(self) -> int:
        return len(self.discarded_blocks)


class ITokenBudgetAllocator(ABC):

    @property
    @abstractmethod
    def allocator_name(self) -> str:
        ...

    @abstractmethod
    def allocate(
        self,
        ranked_blocks: List[RankedContextBlock],
        config: Optional[BudgetConfig] = None,
        strategy: Optional[StrategyConfig] = None,
    ) -> AllocationResult:
        ...
