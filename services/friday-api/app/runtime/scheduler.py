import time
import asyncio
from typing import Optional, List, Dict, Any, Set, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class SchedulingDecision:
    workflow_order: List[str]
    deferred: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    reason: str = ""


class AdaptiveScheduler:
    """Runtime scheduler that reorders remaining steps based on context.

    Capabilities:
    - Reorder remaining workflows
    - Defer low-priority work
    - Execute independent work earlier
    - Skip already-satisfied goals
    - React to new runtime context (latency, failures, confidence)

    Never restarts the entire mission — only reorders remaining work.
    """

    def __init__(self, planner: Any = None) -> None:
        self._planner = planner
        self._decisions: List[SchedulingDecision] = []
        self._reordering_count = 0
        self._deferred_count = 0
        self._skipped_count = 0
        self._total_decisions = 0

    async def reorder(
        self,
        mission_id: str,
        pending_workflows: List[str],
        completed_workflows: Set[str],
        failed_workflows: Set[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> SchedulingDecision:
        self._total_decisions += 1

        if not pending_workflows:
            return SchedulingDecision(
                workflow_order=[], reason="No pending workflows"
            )

        ctx = context or {}
        latency_map = ctx.get("latency_map", {})
        priority_map = ctx.get("priority_map", {})

        remaining = [
            wf for wf in pending_workflows
            if wf not in completed_workflows and wf not in failed_workflows
        ]

        if not remaining:
            return SchedulingDecision(
                workflow_order=[], reason="All workflows completed"
            )

        deferred = []
        skipped = []

        ordered = list(remaining)

        if priority_map:
            ordered.sort(
                key=lambda wf: priority_map.get(wf, 5)
            )

        if latency_map:
            fast_first = sorted(
                ordered,
                key=lambda wf: latency_map.get(wf, float("inf")),
            )
            ordered = fast_first

        deferred_wfs = [
            wf for wf in ordered
            if priority_map.get(wf, 5) >= 8
        ]
        if deferred_wfs and len(ordered) > 2:
            deferred = deferred_wfs
            ordered = [wf for wf in ordered if wf not in deferred]
            self._deferred_count += len(deferred)

        independent = self._find_independent_workflows(ordered)
        if independent and len(independent) > 1:
            ordered = independent + [wf for wf in ordered if wf not in independent]

        satisfied = self._check_already_satisfied(ordered, ctx)
        if satisfied:
            skipped = satisfied
            ordered = [wf for wf in ordered if wf not in satisfied]
            self._skipped_count += len(skipped)

        decision = SchedulingDecision(
            workflow_order=ordered,
            deferred=deferred,
            skipped=skipped,
            reason=(
                f"Reordered {len(ordered)} workflows"
                f"{f', deferred {len(deferred)}' if deferred else ''}"
                f"{f', skipped {len(skipped)}' if skipped else ''}"
            ),
        )
        self._decisions.append(decision)
        self._reordering_count += 1

        logger.info(
            f"AdaptiveScheduler: {decision.reason} "
            f"(mission={mission_id[:8]})"
        )
        return decision

    def _find_independent_workflows(self, workflows: List[str]) -> List[str]:
        if self._planner and hasattr(self._planner, "plan_sequential"):
            return []
        return workflows[:1] if len(workflows) > 1 else []

    def _check_already_satisfied(
        self, workflows: List[str], context: Dict[str, Any]
    ) -> List[str]:
        satisfied_keywords = context.get("satisfied_keywords", "")
        if not satisfied_keywords:
            return []
        skipped = []
        for wf in workflows:
            wf_lower = wf.lower()
            for kw in satisfied_keywords.lower().split(","):
                kw = kw.strip()
                if kw and kw in wf_lower:
                    skipped.append(wf)
                    break
        return skipped

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_decisions": self._total_decisions,
            "reorderings": self._reordering_count,
            "deferred_count": self._deferred_count,
            "skipped_count": self._skipped_count,
        }
