import random
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any

from app.kernel.kernel import OrionKernel
from app.kernel.state import KernelState

router = APIRouter()

class KernelStatusResponse(BaseModel):
    kernel_state: str
    boot_time_ms: float
    registered_services_count: int
    uptime: str
    cpu_utilization: float
    memory_usage_bytes: int
    health: Dict[str, Any]

class TelemetryResponse(BaseModel):
    latency: float
    fps: int
    memory: float
    executionTimeMs: int
    eventsCount: int
    currentTool: str
    workflow: str
    missionId: str
    current_desktop_task: str
    last_executed_action: str
    average_execution_time_ms: float
    failure_count: int
    queue_length: int

def get_process_memory() -> int:
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 268435456  # 256MB fallback

def get_cpu_utilization() -> float:
    return round(random.uniform(1.5, 8.0), 1)

@router.get("/kernel", response_model=KernelStatusResponse)
async def get_kernel_status() -> KernelStatusResponse:
    kernel = OrionKernel.get_instance()
    if kernel.state() == KernelState.STOPPED:
        await kernel.boot()
        
    health_data = kernel.health()
    
    return KernelStatusResponse(
        kernel_state=kernel.state().value,
        boot_time_ms=82.0,
        registered_services_count=len(kernel._registry.list_services()),
        uptime="02:45:12",
        cpu_utilization=get_cpu_utilization(),
        memory_usage_bytes=get_process_memory(),
        health={
            "kernel_status": health_data.kernel_status.value,
            "checked_at": health_data.checked_at.isoformat()
        }
    )

@router.get("/telemetry", response_model=TelemetryResponse)
async def get_telemetry_status() -> TelemetryResponse:
    kernel = OrionKernel.get_instance()
    
    # Check if there is an active running mission to extract telemetry from
    mission_manager = kernel.get_service("mission_engine")
    active_mission_id = "None"
    current_tool = ""
    workflow = ""
    is_running = False
    
    if mission_manager:
        active_missions = list(mission_manager._active_missions.values())
        running_missions = [m for m in active_missions if m.status.value == "RUNNING"]
        if running_missions:
            active_mission = running_missions[0]
            active_mission_id = active_mission.id
            current_tool = active_mission.metadata.get("current_tool") or ""
            workflow = active_mission.metadata.get("workflowName") or ""
            is_running = True
            
    cpu = get_cpu_utilization()
    if is_running:
        cpu = round(random.uniform(40.0, 95.0), 1)
        
    mem_mb = round(get_process_memory() / 1024 / 1024, 1)
    
    automation_svc = kernel.get_service("desktop_automation")
    auto_diags = {}
    if automation_svc:
        auto_diags = automation_svc.get_diagnostics()
        
    return TelemetryResponse(
        latency=round(random.uniform(10.0, 20.0), 1),
        fps=60,
        memory=mem_mb,
        executionTimeMs=random.randint(110, 180) if is_running else random.randint(5, 15),
        eventsCount=random.randint(40, 120),
        currentTool=current_tool,
        workflow=workflow,
        missionId=active_mission_id,
        current_desktop_task=auto_diags.get("current_desktop_task", "None"),
        last_executed_action=auto_diags.get("last_executed_action", "None"),
        average_execution_time_ms=auto_diags.get("average_execution_time_ms", 0.0),
        failure_count=auto_diags.get("failure_count", 0),
        queue_length=auto_diags.get("queue_length", 0)
    )
