from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from loguru import logger

from app.mission_engine import (
    Mission, MissionState, MissionExecutor,
    CheckpointManager, MissionStore,
)
from app.runtime.scheduler import AdaptiveScheduler
from app.runtime.monitor import ExecutionMonitor
from app.runtime.reflection import ReflectionEngine

router = APIRouter()


def _get_executor() -> MissionExecutor:
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    executor = kernel.get_service("mission_engine_v2") if kernel else None
    if not executor:
        raise HTTPException(status_code=503, detail="MissionEngine not available")
    return executor


def _get_scheduler() -> AdaptiveScheduler:
    return AdaptiveScheduler()


def _get_monitor() -> ExecutionMonitor:
    return ExecutionMonitor()


def _get_reflection() -> ReflectionEngine:
    return ReflectionEngine()


@router.get("/runtime/active")
async def runtime_active() -> Dict[str, Any]:
    """List all active missions with progress."""
    executor = _get_executor()
    missions = executor.list_missions()

    active = [
        m for m in missions
        if m.state in (MissionState.RUNNING, MissionState.PAUSED)
    ]

    return {
        "active_count": len(active),
        "missions": [
            {
                "mission_id": m.id,
                "name": m.name,
                "state": m.state.value,
                "priority": m.priority.value if hasattr(m, "priority") else "medium",
                "progress": executor.get_progress(m.id).progress_pct,
                "completed_workflows": len(
                    executor._completed_workflows.get(m.id, set())
                ),
                "total_workflows": len(m.workflow_ids),
                "duration_ms": m.duration_ms,
            }
            for m in active
        ],
    }


@router.get("/runtime/checkpoints")
async def runtime_checkpoints(
    mission_id: Optional[str] = Query(None, description="Filter by mission ID"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Retrieve checkpoints across all missions."""
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    cp_manager = None
    if kernel:
        me = kernel.get_service("mission_engine")
        if me and hasattr(me, "_checkpoints"):
            cp_manager = me._checkpoints

    if not cp_manager:
        cp_manager = CheckpointManager()

    if mission_id:
        cps = cp_manager.get_mission_checkpoints(mission_id)
    else:
        cps = [
            cp for mid in set(
                k for k in dir(cp_manager) if not k.startswith("_")
            )
        ]
        cps = []
        if hasattr(cp_manager, "_checkpoints"):
            cps = list(cp_manager._checkpoints.values())

    return {
        "total_checkpoints": len(cps),
        "checkpoints": [
            {
                "id": cp.id,
                "mission_id": cp.mission_id,
                "state": cp.mission_state.value,
                "completed_workflows": len(cp.completed_workflows),
                "failed_workflows": len(cp.failed_workflows),
                "timestamp": cp.timestamp.isoformat() if hasattr(cp.timestamp, "isoformat") else str(cp.timestamp),
            }
            for cp in cps[:limit]
        ],
    }


@router.get("/runtime/reflections")
async def runtime_reflections(
    mission_id: Optional[str] = Query(None, description="Filter by mission ID"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Retrieve stored reflections."""
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    store = None
    if kernel:
        me = kernel.get_service("mission_engine")
        if me and hasattr(me, "_store"):
            store = me._store

    reflections = []
    if store and hasattr(store, "load_reflection"):
        if mission_id:
            ref = store.load_reflection(mission_id)
            if ref:
                reflections = [ref]
        else:
            for mid in store.list_missions():
                ref = store.load_reflection(mid)
                if ref:
                    reflections.append(ref)
                    if len(reflections) >= limit:
                        break

    scheduler = _get_scheduler()
    monitor = _get_monitor()

    return {
        "reflections_count": len(reflections),
        "reflections": reflections[:limit],
        "scheduler_stats": scheduler.get_stats(),
        "monitor_stats": monitor.get_stats(),
    }


@router.get("/runtime/execution")
async def runtime_execution(
    mission_id: str = Query(..., description="Mission ID"),
) -> Dict[str, Any]:
    """Detailed execution state for a specific mission."""
    executor = _get_executor()
    mission = executor.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")

    progress = executor.get_progress(mission_id)
    context = executor.get_mission_context(mission_id)

    monitor = _get_monitor()
    snapshot = monitor.snapshot(mission_id)

    return {
        "mission": {
            "id": mission.id,
            "name": mission.name,
            "state": mission.state.value,
            "priority": mission.priority.value if hasattr(mission, "priority") else "medium",
            "duration_ms": mission.duration_ms,
            "error": mission.error,
        },
        "progress": {
            "total_workflows": progress.total_workflows,
            "completed": progress.completed,
            "failed": progress.failed,
            "running": progress.running,
            "remaining": progress.remaining,
            "progress_pct": progress.progress_pct,
        },
        "completed_workflows": list(executor._completed_workflows.get(mission_id, set())),
        "failed_workflows": list(executor._failed_workflows.get(mission_id, set())),
        "monitor": {
            "tool_failures": snapshot.tool_failures,
            "total_latency_ms": snapshot.total_latency_ms,
            "timeouts": snapshot.active_timeouts,
            "avg_confidence": snapshot.avg_confidence,
            "warnings": snapshot.warnings,
        },
    }


@router.get("/runtime/history")
async def runtime_history(
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> Dict[str, Any]:
    """Historical mission data with telemetry and reflections."""
    executor = _get_executor()
    missions = executor.list_missions()

    if status:
        try:
            target = MissionState(status)
            missions = [m for m in missions if m.state == target]
        except ValueError:
            pass

    missions.sort(key=lambda m: m.created_at.timestamp() if hasattr(m.created_at, "timestamp") else 0, reverse=True)

    monitor = _get_monitor()
    scheduler = _get_scheduler()

    return {
        "total_missions": len(missions),
        "missions": [
            {
                "mission_id": m.id,
                "name": m.name,
                "state": m.state.value,
                "duration_ms": m.duration_ms,
                "workflow_count": len(m.workflow_ids),
                "error": m.error,
            }
            for m in missions[:limit]
        ],
        "scheduler_stats": scheduler.get_stats(),
        "monitor_stats": monitor.get_stats(),
        "executor_health": executor.health(),
    }
