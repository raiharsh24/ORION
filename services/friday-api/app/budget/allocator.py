from typing import List, Optional
from loguru import logger

from app.context.base import StrategyConfig
from app.ranking.base import RankedContextBlock
from app.budget.base import (
    ITokenBudgetAllocator,
    BudgetConfig,
    BudgetReport,
    AllocatedBlock,
    AllocationResult,
    DEFAULT_MODEL,
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MAX_OUTPUT,
    MODEL_LIMITS,
)
from app.budget.events import TokenBudgetAllocated
from app.events.bus import EventBus


class AdaptiveTokenBudgetAllocator(ITokenBudgetAllocator):

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._running = False

    @property
    def allocator_name(self) -> str:
        return "token_budget_allocator"

    async def start(self) -> None:
        self._running = True
        logger.info("AdaptiveTokenBudgetAllocator started.")

    async def shutdown(self) -> None:
        self._running = False
        logger.info("AdaptiveTokenBudgetAllocator shut down.")

    def health(self):
        return {
            "status": "HEALTHY",
            "details": {
                "allocator_name": self.allocator_name,
                "running": self._running,
            },
        }

    def allocate(
        self,
        ranked_blocks: List[RankedContextBlock],
        config: Optional[BudgetConfig] = None,
        strategy: Optional[StrategyConfig] = None,
    ) -> AllocationResult:
        effective_config = config or BudgetConfig.for_model(DEFAULT_MODEL)
        rank_count = len(ranked_blocks)

        total_budget = effective_config.context_window
        reserved = (
            effective_config.reserved_response_tokens
            + effective_config.system_prompt_reservation
            + effective_config.conversation_history_reservation
        )
        available = total_budget - reserved
        if available < 0:
            available = 0

        self._publish_started(effective_config, rank_count)

        if not ranked_blocks or available <= 0:
            result = AllocationResult(
                selected_blocks=[],
                discarded_blocks=list(ranked_blocks),
                report=BudgetReport(
                    total_budget=total_budget,
                    reserved_tokens=reserved,
                    allocated_tokens=0,
                    discarded_tokens=sum(b.block.estimated_tokens for b in ranked_blocks),
                    utilization_percentage=0.0,
                    selected_blocks=0,
                    discarded_blocks=rank_count,
                    total_blocks_input=rank_count,
                ),
            )
            self._publish_completed(result.report, effective_config.model_name)
            return result

        strategy_ratio = self._resolve_strategy_ratio(strategy)
        strategy_budget = int(available * strategy_ratio)
        if strategy_budget <= 0:
            strategy_budget = available

        selected: List[AllocatedBlock] = []
        discarded: List[RankedContextBlock] = []
        remaining = strategy_budget

        for rcb in ranked_blocks:
            if remaining <= 0:
                discarded.append(rcb)
                continue

            token_estimate = max(rcb.block.estimated_tokens, 1)
            guaranteed = min(effective_config.min_guaranteed_per_block, remaining)

            if guaranteed < effective_config.min_guaranteed_per_block and remaining < effective_config.min_guaranteed_per_block:
                if remaining < token_estimate and selected:
                    discarded.append(rcb)
                    continue

            alloc = self._proportional_allocation(
                token_estimate, remaining, effective_config.max_per_block,
                effective_config.min_guaranteed_per_block,
                strategy_budget, rank_count,
            )
            alloc = min(alloc, remaining)
            alloc = max(alloc, 0)

            if alloc == 0:
                discarded.append(rcb)
                continue

            is_truncated = alloc < token_estimate
            selected.append(AllocatedBlock(
                block=rcb,
                allocated_tokens=alloc,
                is_truncated=is_truncated,
            ))
            remaining -= alloc

        allocated_tokens = sum(a.allocated_tokens for a in selected)
        discarded_tokens = sum(b.block.estimated_tokens for b in discarded)
        used = allocated_tokens + reserved
        utilization = round((allocated_tokens / strategy_budget) * 100, 2) if strategy_budget > 0 else 0.0

        report = BudgetReport(
            total_budget=total_budget,
            reserved_tokens=reserved,
            allocated_tokens=allocated_tokens,
            discarded_tokens=discarded_tokens,
            utilization_percentage=utilization,
            selected_blocks=len(selected),
            discarded_blocks=len(discarded),
            total_blocks_input=rank_count,
            details={
                "model": effective_config.model_name,
                "strategy_budget": strategy_budget,
                "remaining_after_allocation": remaining,
                "strategy_ratio": strategy_ratio,
            },
        )
        result = AllocationResult(
            selected_blocks=selected,
            discarded_blocks=discarded,
            report=report,
        )

        self._publish_completed(report, effective_config.model_name)
        return result

    @staticmethod
    def _proportional_allocation(
        token_estimate: int,
        remaining: int,
        max_per_block: int,
        min_guaranteed: int,
        total_budget: int,
        block_count: int,
    ) -> int:
        if block_count == 0:
            return 0

        proportional = int(remaining * (token_estimate / max(1, total_budget)))
        alloc = max(proportional, min_guaranteed)
        return min(alloc, max_per_block, remaining)

    @staticmethod
    def _resolve_strategy_ratio(strategy: Optional[StrategyConfig]) -> float:
        if strategy is None:
            return 1.0
        tb = strategy.token_budget
        sub_budgets = tb.working_memory + tb.retrieved_context + tb.instructions
        total = tb.total
        if total <= 0:
            return 1.0
        ratio = (sub_budgets + tb.conversation_history + tb.system) / total
        return max(0.1, min(ratio, 1.0))

    def _publish_started(self, config: BudgetConfig, block_count: int) -> None:
        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    TokenBudgetAllocated(
                        total_budget=config.context_window,
                        allocated_tokens=0,
                        selected_blocks=0,
                        discarded_blocks=0,
                        utilization_percentage=0.0,
                        model_name=config.model_name,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish TokenBudgetAllocated start: {e}")

    def _publish_completed(self, report: BudgetReport, model_name: str) -> None:
        if self._running and self._event_bus:
            try:
                self._event_bus.publish_background(
                    TokenBudgetAllocated(
                        total_budget=report.total_budget,
                        allocated_tokens=report.allocated_tokens,
                        selected_blocks=report.selected_blocks,
                        discarded_blocks=report.discarded_blocks,
                        utilization_percentage=report.utilization_percentage,
                        model_name=model_name,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish TokenBudgetAllocated completion: {e}")
