from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

router = APIRouter()


class MissionLogEntry(BaseModel):
    stage: str
    level: str
    message: str
    timestamp: str


class MissionStageDetail(BaseModel):
    name: str
    status: str
    error: Optional[str] = None
    duration_ms: float = 0.0


class MissionDetail(BaseModel):
    mission_id: str
    user_request: str
    intent: str
    status: str
    current_stage: Optional[str] = None
    stages: List[MissionStageDetail] = []
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    plan_id: Optional[str] = None
    goal_ids: List[str] = []
    logs: List[MissionLogEntry] = []


class StatusToggleResponse(BaseModel):
    success: bool
    mission_id: str
    status: str


class RuntimeHealthResponse(BaseModel):
    status: str
    running_missions: int
    queued_missions: int
    paused_missions: int
    completed_missions: int
    failed_missions: int
    uptime_hours: float
    success_rate: float
    recovery_success_rate: float
    total_retries: int
    total_recoveries: int
    max_concurrent: int


class QueueStatusResponse(BaseModel):
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    max_concurrent: int


async def get_mission_runtime():
    kernel = FridayKernel.get_instance()
    if kernel.state() != KernelState.READY:
        await kernel.boot()
    runtime = kernel.get_service("mission_runtime")
    if not runtime:
        raise HTTPException(status_code=500, detail="Mission Runtime service not registered")
    return runtime


def _mission_to_detail(mission: Any, runtime: Any) -> MissionDetail:
    logs: List[Dict[str, Any]] = []
    if hasattr(mission, "metadata") and isinstance(mission.metadata, dict):
        stored_logs = mission.metadata.get("_logs", [])
        for entry in stored_logs:
            logs.append(MissionLogEntry(
                stage=entry.get("stage", ""),
                level=entry.get("level", "INFO"),
                message=entry.get("message", ""),
                timestamp=entry.get("timestamp", ""),
            ))

    stages = []
    for s in getattr(mission, "stages", []):
        stages.append(MissionStageDetail(
            name=s.name,
            status=s.status,
            error=s.error,
            duration_ms=s.duration_ms,
        ))

    telemetry = None
    if runtime:
        telemetry = runtime.get_telemetry(mission.mission_id)

    return MissionDetail(
        mission_id=mission.mission_id,
        user_request=mission.user_request,
        intent=mission.intent,
        status=mission.status,
        current_stage=mission.current_stage,
        stages=stages,
        created_at=str(mission.created_at) if hasattr(mission, "created_at") and mission.created_at else "",
        updated_at=str(mission.updated_at) if hasattr(mission, "updated_at") and mission.updated_at else "",
        completed_at=str(mission.completed_at) if hasattr(mission, "completed_at") and mission.completed_at else None,
        duration_ms=mission.total_duration_ms if hasattr(mission, "total_duration_ms") else 0.0,
        error=mission.error,
        plan_id=getattr(mission, "plan_id", None),
        goal_ids=getattr(mission, "goal_ids", []),
        logs=logs,
    )


@router.get("/runtime/missions", response_model=List[MissionDetail])
async def list_runtime_missions(
    runtime=Depends(get_mission_runtime),
) -> List[MissionDetail]:
    missions = runtime.list_missions()
    return [_mission_to_detail(m, runtime) for m in missions]


@router.get("/runtime/missions/{mission_id}", response_model=MissionDetail)
async def get_runtime_mission(
    mission_id: str,
    runtime=Depends(get_mission_runtime),
) -> MissionDetail:
    mission = runtime.get_mission(mission_id)
    if not mission:
        status = runtime.get_status(mission_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
        return MissionDetail(
            mission_id=mission_id,
            user_request="",
            intent="",
            status=status,
        )
    return _mission_to_detail(mission, runtime)


@router.get("/runtime/missions/{mission_id}/logs", response_model=List[MissionLogEntry])
async def get_mission_logs(
    mission_id: str,
    runtime=Depends(get_mission_runtime),
) -> List[MissionLogEntry]:
    mission = runtime.get_mission(mission_id)
    if not mission:
        status = runtime.get_status(mission_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
        return []

    logs: List[MissionLogEntry] = []
    if hasattr(mission, "metadata") and isinstance(mission.metadata, dict):
        stored_logs = mission.metadata.get("_logs", [])
        for entry in stored_logs:
            logs.append(MissionLogEntry(
                stage=entry.get("stage", ""),
                level=entry.get("level", "INFO"),
                message=entry.get("message", ""),
                timestamp=entry.get("timestamp", ""),
            ))
    return logs


@router.post("/runtime/missions/{mission_id}/pause", response_model=StatusToggleResponse)
async def pause_runtime_mission(
    mission_id: str,
    runtime=Depends(get_mission_runtime),
) -> StatusToggleResponse:
    success = await runtime.pause(mission_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot pause mission '{mission_id}'")
    return StatusToggleResponse(
        success=True,
        mission_id=mission_id,
        status=runtime.get_status(mission_id) or "paused",
    )


@router.post("/runtime/missions/{mission_id}/resume", response_model=StatusToggleResponse)
async def resume_runtime_mission(
    mission_id: str,
    runtime=Depends(get_mission_runtime),
) -> StatusToggleResponse:
    success = await runtime.resume(mission_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot resume mission '{mission_id}'")
    return StatusToggleResponse(
        success=True,
        mission_id=mission_id,
        status=runtime.get_status(mission_id) or "running",
    )


@router.post("/runtime/missions/{mission_id}/cancel", response_model=StatusToggleResponse)
async def cancel_runtime_mission(
    mission_id: str,
    runtime=Depends(get_mission_runtime),
) -> StatusToggleResponse:
    success = await runtime.cancel(mission_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot cancel mission '{mission_id}'")
    return StatusToggleResponse(
        success=True,
        mission_id=mission_id,
        status=runtime.get_status(mission_id) or "cancelled",
    )


@router.post("/runtime/missions/{mission_id}/retry", response_model=StatusToggleResponse)
async def retry_runtime_mission(
    mission_id: str,
    runtime=Depends(get_mission_runtime),
) -> StatusToggleResponse:
    success = await runtime.retry(mission_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Cannot retry mission '{mission_id}'")
    return StatusToggleResponse(
        success=True,
        mission_id=mission_id,
        status=runtime.get_status(mission_id) or "running",
    )


@router.get("/runtime/health", response_model=RuntimeHealthResponse)
async def runtime_health(
    runtime=Depends(get_mission_runtime),
) -> RuntimeHealthResponse:
    h = runtime.health()
    return RuntimeHealthResponse(
        status=h.status,
        running_missions=h.running_missions,
        queued_missions=h.queued_missions,
        paused_missions=h.paused_missions,
        completed_missions=h.completed_missions,
        failed_missions=h.failed_missions,
        uptime_hours=h.uptime_hours,
        success_rate=h.success_rate,
        recovery_success_rate=h.recovery_success_rate,
        total_retries=h.total_retries,
        total_recoveries=h.total_recoveries,
        max_concurrent=h.max_concurrent,
    )


@router.get("/runtime/queue", response_model=QueueStatusResponse)
async def runtime_queue(
    runtime=Depends(get_mission_runtime),
) -> QueueStatusResponse:
    qs = runtime.queue_status()
    return QueueStatusResponse(
        queued=qs.queued,
        running=qs.running,
        completed=qs.completed,
        failed=qs.failed,
        cancelled=qs.cancelled,
        max_concurrent=qs.max_concurrent,
    )
