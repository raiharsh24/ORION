from typing import Dict, Any, Optional
from app.mission_engine.base import (
    Mission, MissionState, MissionContext, MissionResult, MissionTelemetry,
)


def build_mission_result(
    mission: Mission,
    context: MissionContext,
    workflow_results: Dict[str, Any],
    telemetry: Optional[MissionTelemetry] = None,
) -> MissionResult:
    completed = sum(
        1 for wr in workflow_results.values()
        if isinstance(wr, dict) and wr.get("status") == "completed"
    )
    failed = sum(
        1 for wr in workflow_results.values()
        if isinstance(wr, dict) and wr.get("status") == "failed"
    )

    t = telemetry or MissionTelemetry()
    t.completed_workflows = completed
    t.failed_workflows = failed
    t.remaining_workflows = len(mission.workflow_ids) - completed - failed

    return MissionResult(
        mission_id=mission.id,
        mission_name=mission.name,
        status=mission.state,
        workflow_results=workflow_results,
        total_duration_ms=mission.duration_ms,
        total_workflows=len(mission.workflow_ids),
        completed_workflows=completed,
        failed_workflows=failed,
        telemetry=t,
        error=mission.error,
        errors=[mission.error] if mission.error else [],
        final_context=context,
    )
