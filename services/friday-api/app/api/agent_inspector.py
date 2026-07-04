from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from loguru import logger

router = APIRouter()


def _get_orchestrator() -> Any:
    from app.agent_orchestration.orchestrator import AgentOrchestrator
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    orch = kernel.get_service("agent_orchestrator") if kernel else None
    if not orch:
        orch = getattr(kernel, "_agent_orchestrator", None) if kernel else None
    if not orch:
        orch = AgentOrchestrator()
    return orch


@router.get("/agents")
async def list_agents() -> Dict[str, Any]:
    """List all registered agents with status."""
    orch = _get_orchestrator()
    agents = orch.list_agents()
    return {
        "total_agents": len(agents),
        "agents": agents,
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> Dict[str, Any]:
    """Get detailed status for a specific agent."""
    orch = _get_orchestrator()
    status = orch.get_agent_status(agent_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return status


@router.get("/agents/metrics")
async def agent_metrics() -> Dict[str, Any]:
    """Get agent utilization, delegation, and parallel execution metrics."""
    orch = _get_orchestrator()
    return orch.get_metrics().get_summary()


@router.get("/agents/orchestrator/health")
async def orchestrator_health() -> Dict[str, Any]:
    """Get orchestrator health status."""
    orch = _get_orchestrator()
    return orch.health()


@router.get("/agents/approvals")
async def list_pending_approvals() -> Dict[str, Any]:
    """List all pending human approval requests."""
    orch = _get_orchestrator()
    oversight = orch.get_human_oversight()
    return {
        "pending_count": len(oversight.list_pending()),
        "pending": oversight.list_pending(),
        "stats": oversight.get_stats(),
    }


@router.post("/agents/approvals/{mission_id}/approve")
async def approve_mission(mission_id: str) -> Dict[str, Any]:
    """Approve a mission for execution."""
    orch = _get_orchestrator()
    oversight = orch.get_human_oversight()
    success = await oversight.approve(mission_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval for mission '{mission_id}'",
        )
    return {"status": "approved", "mission_id": mission_id}


@router.post("/agents/approvals/{mission_id}/deny")
async def deny_mission(mission_id: str, reason: str = "") -> Dict[str, Any]:
    """Deny a mission execution request."""
    orch = _get_orchestrator()
    oversight = orch.get_human_oversight()
    success = await oversight.deny(mission_id, reason=reason)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval for mission '{mission_id}'",
        )
    return {"status": "denied", "mission_id": mission_id, "reason": reason}


@router.post("/agents/delegate")
async def delegate_objective(
    objective: str = Query(..., description="The high-level objective"),
    description: str = Query("", description="Optional description"),
    require_approval: bool = Query(False, description="Require human approval"),
    parallel: bool = Query(True, description="Execute independent sub-missions in parallel"),
) -> Dict[str, Any]:
    """Delegate a high-level objective to the agent orchestration system."""
    orch = _get_orchestrator()
    result = await orch.plan_and_delegate(
        objective=objective,
        description=description,
        require_approval=require_approval,
        parallel=parallel,
    )
    return result


@router.post("/agents/missions/{mission_id}/pause")
async def pause_mission(mission_id: str) -> Dict[str, Any]:
    """Pause an agent mission."""
    orch = _get_orchestrator()
    success = await orch.pause_mission(mission_id)
    return {"status": "paused" if success else "failed", "mission_id": mission_id}


@router.post("/agents/missions/{mission_id}/resume")
async def resume_mission(mission_id: str) -> Dict[str, Any]:
    """Resume a paused agent mission."""
    orch = _get_orchestrator()
    success = await orch.resume_mission(mission_id)
    return {"status": "resumed" if success else "failed", "mission_id": mission_id}


@router.post("/agents/missions/{mission_id}/cancel")
async def cancel_mission(mission_id: str) -> Dict[str, Any]:
    """Cancel an agent mission."""
    orch = _get_orchestrator()
    success = await orch.cancel_mission(mission_id)
    return {"status": "cancelled" if success else "failed", "mission_id": mission_id}


@router.get("/agents/shared-context/{mission_id}")
async def get_shared_context(mission_id: str) -> Dict[str, Any]:
    """Get the shared mission context for a goal/mission."""
    orch = _get_orchestrator()
    ctx = orch.get_shared_context(mission_id)
    if not ctx:
        raise HTTPException(
            status_code=404,
            detail=f"Shared context for '{mission_id}' not found",
        )
    return {
        "mission_id": ctx.mission_id,
        "shared_data": ctx.get_all_shared(),
        "permissions": {
            "allowed_tools": ctx.permissions.allowed_tools,
            "denied_tools": ctx.permissions.denied_tools,
        },
        "health": ctx.health(),
    }
