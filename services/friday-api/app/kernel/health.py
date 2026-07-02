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
    workflow_runtime: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="workflow_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    intent_analyzer: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="intent_analyzer", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    strategy_manager: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="strategy_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    extractor_registry: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="extractor_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    context_ranker: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="context_ranker", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    token_allocator: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="token_allocator", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    context_validator: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="context_validator", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    context_compressor: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="context_compressor", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    prompt_assembler: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="prompt_assembler", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    pipeline_orchestrator: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="pipeline_orchestrator", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    universal_tool_registry: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="universal_tool_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    tool_selection_engine: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="tool_selection_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    tool_execution_engine: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="tool_execution_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    workflow_engine_v2: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="workflow_engine_v2", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    mission_engine_v2: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="mission_engine_v2", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    capability_registry_v2: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="capability_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    capability_resolver: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="capability_resolver", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    plugin_registry: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="plugin_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    plugin_loader: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="plugin_loader", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    plugin_runtime: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="plugin_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    plugin_marketplace: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="plugin_marketplace", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    plugin_security: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="plugin_security", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    agent_framework: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="agent_framework", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    blackboard: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="blackboard", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    coordinator: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="coordinator", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    delegation_manager: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="delegation_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    persistence_manager: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="persistence_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    recovery_manager: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="recovery_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    metrics_collector: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="metrics_collector", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    planning_engine: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="planning_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
    ))
    mission_runtime: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
        name="mission_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
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
                raw = res.get("status", "HEALTHY")
                if isinstance(raw, str):
                    raw = raw.upper()
                return SubsystemHealth(
                    name=name,
                    status=HealthStatus(raw),
                    message=res.get("message"),
                    details=res.get("details", {})
                )
            elif isinstance(res, str):
                return SubsystemHealth(
                    name=name,
                    status=HealthStatus(res.upper())
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
