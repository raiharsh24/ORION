from typing import Dict, List, Optional
from app.workflow_engine.base import (
    WorkflowGraph, WorkflowNode, WorkflowStatus,
    ExecutedNode, WorkflowContext, WorkflowExecutionResult,
)


def build_workflow_report(
    node_results: Dict[str, ExecutedNode],
    context: WorkflowContext,
    total_duration_ms: float,
) -> WorkflowExecutionResult:
    status = WorkflowStatus.COMPLETED
    failed_node: Optional[str] = None
    errors: List[str] = []

    for nid, nr in node_results.items():
        if nr.status == WorkflowStatus.FAILED:
            status = WorkflowStatus.FAILED
            if failed_node is None:
                failed_node = nid
            if nr.error:
                errors.append(f"[{nid}] {nr.error}")
        elif nr.status == WorkflowStatus.CANCELLED:
            if status != WorkflowStatus.FAILED:
                status = WorkflowStatus.CANCELLED

    completed_durations = [
        nr.duration_ms for nr in node_results.values()
        if nr.status == WorkflowStatus.COMPLETED and nr.duration_ms > 0
    ]
    parallelism = round(
        sum(completed_durations) / total_duration_ms / max(len(completed_durations), 1), 4
    ) if completed_durations and total_duration_ms > 0 else 0.0

    critical_path_ms = _compute_critical_path(node_results)

    return WorkflowExecutionResult(
        execution_id=context.execution_id,
        status=status,
        node_results=node_results,
        context=context,
        total_duration_ms=total_duration_ms,
        critical_path_ms=critical_path_ms,
        parallelism=parallelism,
        error=errors[0] if errors else None,
        failed_node_id=failed_node,
        errors=errors,
    )


def _compute_critical_path(node_results: Dict[str, ExecutedNode]) -> float:
    if not node_results:
        return 0.0
    return max(
        (nr.duration_ms for nr in node_results.values()
         if nr.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED)),
        default=0.0,
    )
