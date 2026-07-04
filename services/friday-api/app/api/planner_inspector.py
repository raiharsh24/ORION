from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from loguru import logger

from app.friday.planner_schema import ExecutionPlan
from app.planner.goal_planner import GoalPlanner, GoalPlan
from app.planner.reasoning import ReasoningPipeline, ReasoningResult
from app.planner.confidence import ConfidenceEngine, PlanConfidence
from app.planner.recovery import RecoveryPolicies, RecoveryAttempt
from app.planner.analytics import MissionAnalytics

router = APIRouter()


def _get_planner() -> Any:
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    planner = kernel.get_service("planner_engine") if kernel else None
    if not planner:
        raise HTTPException(status_code=503, detail="PlannerEngine not available")
    return planner


def _get_goal_planner() -> GoalPlanner:
    try:
        planner = _get_planner()
        if hasattr(planner, "_manager"):
            return GoalPlanner()
    except HTTPException:
        pass
    return GoalPlanner()


def _get_reasoning() -> ReasoningPipeline:
    return ReasoningPipeline()


def _get_confidence() -> ConfidenceEngine:
    return ConfidenceEngine()


def _get_recovery() -> RecoveryPolicies:
    try:
        from app.kernel.kernel import FridayKernel
        kernel = FridayKernel.get_instance()
        executor = kernel.get_service("mission_engine") if kernel else None
        return RecoveryPolicies(executor=executor)
    except Exception:
        return RecoveryPolicies()


def _get_analytics() -> MissionAnalytics:
    return MissionAnalytics()


@router.get("/planner/plans")
async def planner_plans(
    goal_id: Optional[str] = Query(None, description="Filter by goal ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """List all goal plans."""
    gp = _get_goal_planner()
    goals = gp.list_goals(status=status)
    if goal_id:
        goal = gp.get_goal(goal_id)
        goals = [goal] if goal else []

    return {
        "total_goals": len(goals),
        "goals": [
            {
                "goal_id": g.goal_id,
                "objective": g.objective[:100],
                "sub_goals_count": len(g.sub_goals),
                "missions_count": len(g.missions),
                "status": g.status,
                "created_at": g.created_at,
                "estimated_duration": g.total_estimated_duration,
            }
            for g in goals[:limit]
        ],
        "stats": gp.get_stats(),
    }


@router.get("/planner/plans/{goal_id}")
async def planner_plan_detail(goal_id: str) -> Dict[str, Any]:
    """Get detail for a goal plan including mission info."""
    gp = _get_goal_planner()
    goal = gp.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal '{goal_id}' not found")

    reasoning = _get_reasoning()
    confidence = _get_confidence()

    return {
        "goal_id": goal.goal_id,
        "objective": goal.objective,
        "description": goal.description,
        "status": goal.status,
        "sub_goals": goal.sub_goals,
        "missions": goal.missions,
        "total_estimated_duration": goal.total_estimated_duration,
        "created_at": goal.created_at,
        "metadata": goal.metadata,
        "reasoning_stats": reasoning.get_stats(),
        "confidence_stats": confidence.get_stats(),
    }


@router.get("/planner/active")
async def planner_active() -> Dict[str, Any]:
    """List all active/pending goal plans and missions."""
    gp = _get_goal_planner()
    active = gp.list_goals(status="planned")
    reasoning = _get_reasoning()

    return {
        "active_goals": len(active),
        "goals": [
            {
                "goal_id": g.goal_id,
                "objective": g.objective[:80],
                "missions_count": len(g.missions),
                "created_at": g.created_at,
            }
            for g in active
        ],
        "total_planned_missions": sum(len(g.missions) for g in active),
    }


@router.get("/planner/history")
async def planner_history(
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Recent reasoning history."""
    reasoning = _get_reasoning()
    results = reasoning.list_results(limit=limit)

    return {
        "total": len(results),
        "results": [
            {
                "reasoning_id": r.reasoning_id,
                "objective": r.objective[:80],
                "stages_count": len(r.stages),
                "total_duration_ms": r.total_duration_ms,
                "overall_summary": r.overall_summary,
                "created_at": r.created_at,
                "stages": [
                    {
                        "stage": s.stage,
                        "summary": s.summary,
                        "duration_ms": s.duration_ms,
                    }
                    for s in r.stages
                ],
            }
            for r in results
        ],
    }


@router.get("/planner/recovery")
async def planner_recovery() -> Dict[str, Any]:
    """Recovery statistics and recent attempts."""
    recovery = _get_recovery()
    return recovery.get_stats()


@router.get("/planner/statistics")
async def planner_statistics() -> Dict[str, Any]:
    """Aggregate planner analytics."""
    analytics = _get_analytics()
    goal_planner = _get_goal_planner()
    reasoning = _get_reasoning()
    confidence = _get_confidence()
    recovery = _get_recovery()

    return {
        "goal_planner": goal_planner.get_stats(),
        "reasoning_pipeline": reasoning.get_stats(),
        "confidence_engine": confidence.get_stats(),
        "recovery_policies": recovery.get_stats(),
        "mission_analytics": analytics.get_summary(),
    }
