from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from app.kernel.kernel import FridayKernel
from app.missions.mission import MissionStatus, Mission
from app.missions.mission_manager import MissionManager, CreateMissionRequest, MissionResponse

router = APIRouter()

class StatusToggleResponse(BaseModel):
    success: bool
    mission_id: str
    status: str

class LogEntryResponse(BaseModel):
    time: str
    level: str
    msg: str

class DetailedMissionResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    priority: str
    type: str
    workflow_id: Optional[str] = None
    progress: float
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    currentStep: str
    steps: List[str]
    durationMs: int
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None
    error: Optional[str] = None
    currentTool: Optional[str] = None
    workflowName: Optional[str] = None
    logs: List[LogEntryResponse]

async def get_mission_manager() -> MissionManager:
    kernel = FridayKernel.get_instance()
    # Ensure kernel is booted
    if kernel.state().value == "STOPPED":
        await kernel.boot()
    manager = kernel.get_service("mission_engine")
    if not manager:
        raise HTTPException(status_code=500, detail="Mission Engine service not registered in Kernel.")
    return manager

async def sync_mission_progress(manager: MissionManager):
    """
    Helper function to dynamically calculate and update progress on running missions
    using a pull-based elapsed time strategy.
    """
    now = datetime.now(timezone.utc)
    for m_id, mission in list(manager._active_missions.items()):
        if mission.status == MissionStatus.RUNNING:
            start_time = manager._start_times.get(m_id)
            if not start_time:
                start_time = now
                manager._start_times[m_id] = start_time
                
            elapsed_seconds = (now - start_time.replace(tzinfo=timezone.utc)).total_seconds()
            progress = min(100.0, elapsed_seconds * 5.0)  # 5% progress per second (20s total run)
            
            mission.progress = progress
            
            steps = mission.metadata.get("steps", ["Init", "Process Tasks", "Verify Output", "Done"])
            step_idx = min(len(steps) - 1, int((progress / 100.0) * len(steps)))
            mission.current_step = steps[step_idx]
            
            # Update metadata logs dynamically during execution
            logs = mission.metadata.setdefault("logs", [])
            last_logged_step = mission.metadata.get("last_logged_step")
            
            if last_logged_step != mission.current_step:
                timestamp = now.strftime("%H:%M:%S")
                logs.append({
                    "time": timestamp,
                    "level": "INFO",
                    "msg": f"Transitioning to step: {mission.current_step}"
                })
                mission.metadata["last_logged_step"] = mission.current_step
                
                # Periodically append a mock debug tool log
                if len(logs) % 2 == 0:
                    tool = mission.metadata.get("current_tool") or "terminal.run_command"
                    logs.append({
                        "time": timestamp,
                        "level": "DEBUG",
                        "msg": f"Invoking tool component: {tool} on workspace targets"
                    })
            
            event_bus = FridayKernel.get_instance().get_service("event_bus")
            from app.events.events import FridayEvent
            
            if progress >= 100.0:
                mission.status = MissionStatus.COMPLETED
                mission.current_step = "Finished"
                mission.updated_at = now
                timestamp = now.strftime("%H:%M:%S")
                logs.append({
                    "time": timestamp,
                    "level": "SUCCESS",
                    "msg": "Workflow completed successfully inside live API backend."
                })
                
                # Also save to persistent history store
                if manager._history:
                    await manager._history.save(mission)
                    
                if event_bus:
                    detailed = map_to_detailed(mission, manager)
                    await event_bus.publish(FridayEvent("MissionCompleted", detailed.model_dump()))
            else:
                if event_bus:
                    detailed = map_to_detailed(mission, manager)
                    await event_bus.publish(FridayEvent("MissionUpdated", detailed.model_dump()))

def map_to_detailed(mission: Mission, manager: MissionManager) -> DetailedMissionResponse:
    # Estimate total elapsed duration in ms
    start_time = manager._start_times.get(mission.id)
    duration_ms = 0
    if start_time:
        end_time = datetime.now(timezone.utc) if mission.status == MissionStatus.RUNNING else mission.updated_at
        duration_ms = int((end_time.replace(tzinfo=timezone.utc) - start_time.replace(tzinfo=timezone.utc)).total_seconds() * 1000)
    
    # Extract properties
    steps = mission.metadata.get("steps", ["Init", "Process Tasks", "Verify Output", "Done"])
    workflow_name = mission.metadata.get("workflowName") or "generic_workflow"
    current_tool = mission.metadata.get("current_tool") if mission.status == MissionStatus.RUNNING else None
    
    # Get logs from metadata
    logs_data = mission.metadata.get("logs") or []
    logs = [LogEntryResponse(**l) for l in logs_data]
    
    return DetailedMissionResponse(
        id=mission.id,
        name=mission.name,
        description=mission.description,
        status=mission.status.value,
        priority=mission.priority.value,
        type=mission.type.value,
        workflow_id=mission.workflow_id,
        progress=mission.progress,
        created_at=mission.created_at,
        updated_at=mission.updated_at,
        metadata=mission.metadata,
        currentStep=mission.current_step or "Pending Queue",
        steps=steps,
        durationMs=max(0, duration_ms),
        startedAt=start_time.strftime("%H:%M:%S") if start_time else None,
        finishedAt=mission.updated_at.strftime("%H:%M:%S") if mission.status in [MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED] else None,
        error=mission.metadata.get("error"),
        currentTool=current_tool,
        workflowName=workflow_name,
        logs=logs
    )

@router.get("/missions", response_model=List[DetailedMissionResponse])
async def list_missions(manager: MissionManager = Depends(get_mission_manager)) -> List[DetailedMissionResponse]:
    await sync_mission_progress(manager)
    # Combine active missions and history archives
    result = []
    
    for m in manager._active_missions.values():
        result.append(map_to_detailed(m, manager))
        
    # Also load from history to support terminated/history missions
    if manager._history:
        history_items = await manager._history.list_all() if hasattr(manager._history, "list_all") else getattr(manager._history, "records", [])
        # Prevent listing active duplicates
        active_ids = {m.id for m in manager._active_missions.values()}
        for hm in history_items:
            if hm.id not in active_ids:
                result.append(map_to_detailed(hm, manager))
                
    return result

@router.get("/missions/{id}", response_model=DetailedMissionResponse)
async def get_mission(id: str, manager: MissionManager = Depends(get_mission_manager)) -> DetailedMissionResponse:
    await sync_mission_progress(manager)
    mission = manager._active_missions.get(id)
    if not mission and manager._history:
        history_items = await manager._history.list_all() if hasattr(manager._history, "list_all") else getattr(manager._history, "records", [])
        for hm in history_items:
            if hm.id == id:
                mission = hm
                break
                
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{id}' not found.")
        
    return map_to_detailed(mission, manager)

@router.post("/missions/{mission_id}/start", response_model=StatusToggleResponse)
async def start_mission(mission_id: str, manager: MissionManager = Depends(get_mission_manager)) -> StatusToggleResponse:
    mission = manager._active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
        
    success = await manager.start_mission(mission_id)
    if success:
        # Initialize logs
        mission.metadata["logs"] = [
            {
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "level": "INFO",
                "msg": f"Started mission: {mission.name}"
            },
            {
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "level": "DEBUG",
                "msg": f"Initializing workflow sequence: {mission.metadata.get('workflowName', 'generic_workflow')}"
            }
        ]
        event_bus = FridayKernel.get_instance().get_service("event_bus")
        if event_bus:
            from app.events.events import FridayEvent
            detailed = map_to_detailed(mission, manager)
            await event_bus.publish(FridayEvent("MissionStarted", detailed.model_dump()))
        
    return StatusToggleResponse(
        success=success,
        mission_id=mission_id,
        status=mission.status.value
    )

@router.post("/missions/{mission_id}/pause", response_model=StatusToggleResponse)
async def pause_mission(mission_id: str, manager: MissionManager = Depends(get_mission_manager)) -> StatusToggleResponse:
    mission = manager._active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
        
    # Standard manager transition
    success = await manager.pause_mission(mission_id)
    if success:
        logs = mission.metadata.setdefault("logs", [])
        logs.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "level": "WARN",
            "msg": "Mission paused by user interaction."
        })
        event_bus = FridayKernel.get_instance().get_service("event_bus")
        if event_bus:
            from app.events.events import FridayEvent
            detailed = map_to_detailed(mission, manager)
            await event_bus.publish(FridayEvent("MissionUpdated", detailed.model_dump()))
        
    return StatusToggleResponse(
        success=success,
        mission_id=mission_id,
        status=mission.status.value
    )

@router.post("/missions/{mission_id}/resume", response_model=StatusToggleResponse)
async def resume_mission(mission_id: str, manager: MissionManager = Depends(get_mission_manager)) -> StatusToggleResponse:
    mission = manager._active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
        
    success = await manager.resume_mission(mission_id)
    if success:
        elapsed_needed = (mission.progress / 5.0)
        manager._start_times[mission_id] = datetime.now(timezone.utc) - timedelta(seconds=elapsed_needed)
        
        logs = mission.metadata.setdefault("logs", [])
        logs.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "level": "INFO",
            "msg": "Mission execution resumed."
        })
        event_bus = FridayKernel.get_instance().get_service("event_bus")
        if event_bus:
            from app.events.events import FridayEvent
            detailed = map_to_detailed(mission, manager)
            await event_bus.publish(FridayEvent("MissionUpdated", detailed.model_dump()))
        
    return StatusToggleResponse(
        success=success,
        mission_id=mission_id,
        status=mission.status.value
    )

@router.post("/missions/{mission_id}/cancel", response_model=StatusToggleResponse)
async def cancel_mission(mission_id: str, manager: MissionManager = Depends(get_mission_manager)) -> StatusToggleResponse:
    mission = manager._active_missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
        
    success = await manager.cancel_mission(mission_id)
    if success:
        logs = mission.metadata.setdefault("logs", [])
        logs.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "level": "ERROR",
            "msg": "Mission execution cancelled by user request."
        })
        event_bus = FridayKernel.get_instance().get_service("event_bus")
        if event_bus:
            from app.events.events import FridayEvent
            detailed = map_to_detailed(mission, manager)
            await event_bus.publish(FridayEvent("MissionCancelled", detailed.model_dump()))
        
    return StatusToggleResponse(
        success=success,
        mission_id=mission_id,
        status=mission.status.value
    )

class ActionConfirmRequest(BaseModel):
    approved: bool

@router.post("/missions/{id}/confirm")
async def confirm_mission_action(id: str, request: ActionConfirmRequest) -> Dict[str, Any]:
    automation = FridayKernel.get_instance().get_service("desktop_automation")
    if not automation:
        raise HTTPException(status_code=500, detail="Desktop Automation Service not registered.")
    
    success = automation.confirm_action(id, request.approved)
    return {
        "success": success,
        "mission_id": id,
        "approved": request.approved
    }
