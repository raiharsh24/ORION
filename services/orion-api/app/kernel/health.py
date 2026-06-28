from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

class HealthStatus(str, Enum):
    """
    Subsystem health status indicators.
    """
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

class SubsystemHealth(BaseModel):
    name: str
    status: HealthStatus
    message: Optional[str] = None
    last_checked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)

class KernelHealth(BaseModel):
    """
    Consolidated health metadata for the central coordinator and all core subsystems.
    """
    kernel_status: HealthStatus
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    planner: SubsystemHealth
    knowledge: SubsystemHealth
    memory: SubsystemHealth
    desktop: SubsystemHealth
    mission: SubsystemHealth
    workflow: SubsystemHealth
    scheduler: SubsystemHealth
    llm: SubsystemHealth
    agents: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="agents", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))

def check_service_health(name: str, service: Any) -> SubsystemHealth:
    """
    Dynamically queries a service's health status.
    Exposes health if the service has a `health()` method.
    Otherwise, defaults to HEALTHY.
    """
    if hasattr(service, "health") and callable(service.health):
        try:
            import inspect
            if inspect.iscoroutinefunction(service.health):
                # We can't await inside a sync health method, but we can check if it returns a coroutine.
                # Since health check here is synchronous, we handle potential async health methods by warning.
                return SubsystemHealth(
                    name=name,
                    status=HealthStatus.WARNING,
                    message="Service health checker is asynchronous; sync sweep returned warning."
                )
            res = service.health()
            if inspect.iscoroutine(res):
                try:
                    res.close()
                except Exception:
                    pass
                return SubsystemHealth(
                    name=name,
                    status=HealthStatus.WARNING,
                    message="Service health checker returned a coroutine (asynchronous); sync sweep returned warning."
                )
            if isinstance(res, SubsystemHealth):
                return res
            elif isinstance(res, dict):
                return SubsystemHealth(
                    name=name,
                    status=HealthStatus(res.get("status", HealthStatus.HEALTHY)),
                    message=res.get("message"),
                    details=res.get("details", {})
                )
            elif isinstance(res, str):
                return SubsystemHealth(
                    name=name,
                    status=HealthStatus(res)
                )
        except Exception as e:
            return SubsystemHealth(
                name=name,
                status=HealthStatus.ERROR,
                message=f"Subsystem diagnostic check failed: {str(e)}"
            )
            
    return SubsystemHealth(
        name=name,
        status=HealthStatus.HEALTHY,
        message="Service operational."
    )
