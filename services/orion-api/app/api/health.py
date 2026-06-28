from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.core.config import settings
from app.kernel.kernel import OrionKernel
from app.kernel.state import KernelState

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    kernel = OrionKernel.get_instance()
    if kernel.state() == KernelState.STOPPED:
        await kernel.boot()
        
    health_data = kernel.health()
    
    services_list = []
    subsystems = ["planner", "knowledge", "memory", "desktop", "mission", "workflow", "scheduler", "llm"]
    for sub in subsystems:
        val = getattr(health_data, sub, None)
        if val:
            services_list.append({
                "name": sub.capitalize() if sub != "llm" else "LLM",
                "status": val.status.value,
                "message": val.message or "Service operational."
            })
            
    telemetry_val = getattr(health_data, "telemetry", None)
    services_list.append({
        "name": "Telemetry",
        "status": telemetry_val.status.value if telemetry_val else "HEALTHY",
        "message": telemetry_val.message if telemetry_val else "Service operational."
    })
            
    return HealthResponse(
        status="online",
        assistant="ORION",
        version=settings.APP_VERSION,
        services=services_list
    )
