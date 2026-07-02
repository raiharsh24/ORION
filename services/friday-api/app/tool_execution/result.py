from datetime import datetime
from typing import Dict, Any, List, Optional
from app.tool_execution.base import (
    ToolExecutionResult, ExecutedTool, ExecutionReport, ExecutionStatus,
)


def build_report(results: List[ExecutedTool]) -> ExecutionReport:
    report = ExecutionReport(
        total_tools=len(results),
        completed=sum(1 for r in results if r.status == ExecutionStatus.COMPLETED),
        failed=sum(1 for r in results if r.status == ExecutionStatus.FAILED),
        cancelled=sum(1 for r in results if r.status == ExecutionStatus.CANCELLED),
        timed_out=sum(1 for r in results if r.status == ExecutionStatus.TIMEOUT),
        skipped=sum(1 for r in results if r.status == ExecutionStatus.SKIPPED),
        errors=[r.error for r in results if r.error],
    )
    if results:
        start = min((r.started_at or datetime.now()).timestamp() for r in results)
        end = max((r.completed_at or r.started_at or datetime.now()).timestamp() for r in results)
        report.total_duration_ms = (end - start) * 1000
    if report.total_duration_ms > 0 and report.completed > 0:
        total_successful_ms = sum(r.duration_ms for r in results if r.success)
        report.parallel_efficiency = round(
            (total_successful_ms / report.total_duration_ms) / report.completed, 4,
        )
    return report
