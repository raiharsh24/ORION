from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.core.config import settings
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    kernel = FridayKernel.get_instance()
    if kernel.state() == KernelState.STOPPED:
        await kernel.boot()

    health_data = kernel.health()

    services_list = []
    subsystems = ["planner", "knowledge", "memory", "desktop", "mission", "workflow", "scheduler", "llm", "agents", "workflow_runtime"]
    for sub in subsystems:
        val = getattr(health_data, sub, None)
        if val:
            services_list.append({
                "name": sub.capitalize() if sub not in ("llm", "workflow_runtime") else sub.replace("_", " ").title(),
                "status": val.status.value,
                "message": val.message or "Service operational."
            })

    return HealthResponse(
        status="online",
        assistant="FRIDAY",
        version=settings.APP_VERSION,
        services=services_list
    )
