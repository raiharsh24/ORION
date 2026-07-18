from typing import Any, Dict, List, Optional

from app.reflection.base import BaseReflectionEngine
from app.reflection.models import ExecutionSnapshot, ReflectionReport


class HeuristicReflectionEngine(BaseReflectionEngine):
    def reflect(self, snapshot: ExecutionSnapshot) -> ReflectionReport:
        what_succeeded: List[str] = []
        what_failed: List[str] = []
        improvements: List[str] = []
        reasons: List[str] = []

        if snapshot.success:
            what_succeeded.append("Tool execution completed without errors")
            what_succeeded.append(
                f"Completed {len(snapshot.completed_tasks)} task(s)"
                if snapshot.completed_tasks
                else "Execution produced output"
            )
        else:
            what_failed.append("Tool execution produced errors")
            what_failed.append(f"Encountered {len(snapshot.errors)} error(s)")
            reasons.append("Errors detected in tool output or execution stage")

        if snapshot.fallback_used:
            what_succeeded.append("Fallback mechanism engaged successfully")
            improvements.append("Consider adjusting primary tool selection confidence threshold")
            reasons.append("Primary tool failed — fallback was required")
        else:
            what_succeeded.append("No fallback needed — primary tool(s) sufficed")

        _assess_confidence(snapshot, what_succeeded, what_failed, improvements, reasons)
        _assess_timing(snapshot, what_succeeded, improvements, reasons)
        _assess_tools(snapshot, what_succeeded, what_failed, improvements, reasons)
        _assess_errors(snapshot, what_failed, improvements, reasons)

        quality = _compute_quality_score(snapshot)

        recommended_ordering = _recommend_ordering(snapshot)

        why = "; ".join(reasons) if reasons else "Execution completed nominally"

        return ReflectionReport(
            execution_id=snapshot.execution_id,
            snapshot=snapshot,
            what_succeeded=what_succeeded,
            what_failed=what_failed,
            why=why,
            possible_improvements=improvements,
            recommended_tool_ordering=recommended_ordering,
            execution_quality_score=quality,
        )


def _assess_confidence(
    snapshot: ExecutionSnapshot,
    succeeded: List[str],
    failed: List[str],
    improvements: List[str],
    reasons: List[str],
) -> None:
    if snapshot.confidence >= 0.8:
        succeeded.append(f"High confidence ({snapshot.confidence:.2f}) in tool selection")
    elif snapshot.confidence >= 0.5:
        succeeded.append(f"Moderate confidence ({snapshot.confidence:.2f}) — acceptable")
    else:
        failed.append(f"Low confidence ({snapshot.confidence:.2f}) in selected tools")
        improvements.append("Improve capability-to-tool matching to raise confidence")
        reasons.append(f"Low confidence ({snapshot.confidence:.2f})")


def _assess_timing(
    snapshot: ExecutionSnapshot,
    succeeded: List[str],
    improvements: List[str],
    reasons: List[str],
) -> None:
    dur = snapshot.execution_duration_ms
    if dur < 1000:
        succeeded.append(f"Fast execution ({dur:.0f}ms)")
    elif dur < 5000:
        succeeded.append(f"Reasonable execution time ({dur:.0f}ms)")
    else:
        improvements.append(f"Optimize slow execution ({dur:.0f}ms) — consider caching or parallel tool calls")
        reasons.append(f"Execution duration ({dur:.0f}ms) exceeded threshold")


def _assess_tools(
    snapshot: ExecutionSnapshot,
    succeeded: List[str],
    failed: List[str],
    improvements: List[str],
    reasons: List[str],
) -> None:
    tools = snapshot.selected_tools
    if not tools:
        failed.append("No tools were selected for execution")
        improvements.append("Ensure capabilities map to at least one registered tool")
        reasons.append("Empty tool selection result")
        return

    succeeded.append(f"{len(tools)} tool(s) selected")

    tool_ids = [t.get("id", "") for t in tools if t.get("id")]
    fallback_tools = [t for t in tools if t.get("is_fallback")]
    if fallback_tools:
        improvements.append(
            f"Promote fallback tools to primary: {', '.join(t.get('id', '') for t in fallback_tools)}"
        )
        reasons.append(f"Fallback tools used: {len(fallback_tools)}")


def _assess_errors(
    snapshot: ExecutionSnapshot,
    failed: List[str],
    improvements: List[str],
    reasons: List[str],
) -> None:
    if snapshot.errors:
        failed.append(f"{len(snapshot.errors)} error(s) recorded")
        for err in snapshot.errors[:3]:
            failed.append(f"  {err}")
        improvements.append("Add retry logic for transient errors")
        improvements.append("Validate tool arguments before execution")
        reasons.append(f"Errors: {'; '.join(snapshot.errors[:3])}")


def _compute_quality_score(snapshot: ExecutionSnapshot) -> float:
    score = 1.0

    if not snapshot.success:
        score -= 0.3

    score -= len(snapshot.errors) * 0.1

    if snapshot.fallback_used:
        score -= 0.15

    if snapshot.confidence < 0.5:
        score -= 0.2
    elif snapshot.confidence < 0.8:
        score -= 0.1

    dur = snapshot.execution_duration_ms
    if dur > 10000:
        score -= 0.15
    elif dur > 5000:
        score -= 0.05

    if not snapshot.selected_tools:
        score -= 0.3

    return max(0.0, min(1.0, score))


def _recommend_ordering(snapshot: ExecutionSnapshot) -> List[str]:
    tools = snapshot.selected_tools
    if not tools:
        return []

    fallbacks = [t.get("id", "") for t in tools if t.get("is_fallback")]
    primaries = [t.get("id", "") for t in tools if not t.get("is_fallback")]

    ordering: List[str] = list(primaries)
    if fallbacks:
        ordering.extend(fallback for fb in fallbacks if (fallback := fb) not in ordering)

    return ordering
