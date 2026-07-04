from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from loguru import logger

router = APIRouter()


def _get_cognitive() -> Any:
    from app.cognitive.cognitive_engine import CognitiveEngine
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    engine = kernel.get_service("cognitive_engine") if kernel else None
    if not engine:
        engine = getattr(kernel, "_cognitive_engine", None) if kernel else None
    if not engine:
        engine = CognitiveEngine()
    return engine


@router.get("/cognitive/health")
async def cognitive_health() -> Dict[str, Any]:
    engine = _get_cognitive()
    return engine.health()


@router.get("/cognitive/context")
async def strategic_context() -> Dict[str, Any]:
    engine = _get_cognitive()
    return engine.get_strategic_context()


@router.post("/cognitive/mission")
async def run_cognitive_mission(
    objective: str = Query(..., description="High-level objective"),
    description: str = Query("", description="Optional description"),
    require_approval: bool = Query(False),
    use_collaboration: bool = Query(True),
    use_scheduler: bool = Query(False),
    delay_seconds: float = Query(0.0),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    return await engine.run_cognitive_mission(
        objective=objective,
        description=description,
        require_approval=require_approval,
        use_collaboration=use_collaboration,
        use_scheduler=use_scheduler,
        delay_seconds=delay_seconds,
    )


@router.get("/cognitive/goals")
async def list_goals(
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    goals = engine.goal_memory.list_goals(status=status, tag=tag)
    return {
        "total": len(goals),
        "goals": [
            {
                "goal_id": g.goal_id,
                "objective": g.objective[:100],
                "status": g.status,
                "progress_pct": g.progress_pct,
                "priority": g.priority,
                "parent_id": g.parent_id,
                "milestones": len(g.milestones),
                "created_at": g.created_at,
            }
            for g in goals
        ],
    }


@router.post("/cognitive/goals")
async def create_goal(
    objective: str = Query(...),
    description: str = Query(""),
    parent_id: Optional[str] = Query(None),
    priority: float = Query(5.0),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    goal = engine.goal_memory.create_goal(
        objective=objective, description=description,
        parent_id=parent_id, priority=priority,
    )
    return {
        "goal_id": goal.goal_id,
        "objective": goal.objective,
        "status": goal.status,
    }


@router.get("/cognitive/goals/{goal_id}")
async def get_goal(goal_id: str) -> Dict[str, Any]:
    engine = _get_cognitive()
    goal = engine.goal_memory.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {
        "goal_id": goal.goal_id,
        "objective": goal.objective,
        "description": goal.description,
        "status": goal.status,
        "progress_pct": goal.progress_pct,
        "priority": goal.priority,
        "parent_id": goal.parent_id,
        "milestones": goal.milestones,
        "tags": goal.tags,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
        "completed_at": goal.completed_at,
    }


@router.get("/cognitive/hierarchy")
async def list_hierarchies() -> Dict[str, Any]:
    engine = _get_cognitive()
    stats = engine.goal_manager.get_stats()
    return {"hierarchies": stats}


@router.post("/cognitive/hierarchy")
async def create_hierarchy(
    objective: str = Query(...),
    description: str = Query(""),
    depth: int = Query(2, ge=1, le=5),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    hierarchy = engine.goal_manager.analyze_and_decompose(
        objective=objective, description=description, depth=depth,
    )
    return {
        "root_id": hierarchy.root_id,
        "node_count": len(hierarchy.nodes),
        "depth": hierarchy.depth,
        "objective": objective,
    }


@router.get("/cognitive/hierarchy/{hierarchy_id}")
async def get_hierarchy(hierarchy_id: str) -> Dict[str, Any]:
    engine = _get_cognitive()
    h = engine.goal_manager.get_hierarchy(hierarchy_id)
    if not h:
        raise HTTPException(status_code=404, detail="Hierarchy not found")
    nodes = []
    for n in h.nodes.values():
        nodes.append({
            "goal_id": n.goal_id,
            "objective": n.objective[:80],
            "parent_id": n.parent_id,
            "children": n.children,
            "status": n.status,
            "priority": n.priority,
            "progress_pct": n.progress_pct,
            "depends_on": n.depends_on,
            "milestones": len(n.milestones),
        })
    return {
        "root_id": h.root_id,
        "depth": h.depth,
        "nodes": nodes,
    }


@router.get("/cognitive/hierarchy/{hierarchy_id}/ready")
async def get_ready_goals(hierarchy_id: str) -> Dict[str, Any]:
    engine = _get_cognitive()
    ready = engine.goal_manager.get_ready_goals(hierarchy_id)
    return {
        "count": len(ready),
        "goals": [
            {"goal_id": g.goal_id, "objective": g.objective[:80],
             "priority": g.priority, "depends_on": g.depends_on}
            for g in ready
        ],
    }


@router.post("/cognitive/hierarchy/{hierarchy_id}/goals/{goal_id}/status")
async def update_goal_status(
    hierarchy_id: str, goal_id: str,
    status: str = Query(...),
    progress_pct: Optional[float] = Query(None),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    success = engine.goal_manager.update_goal_status(
        hierarchy_id, goal_id, status, progress_pct=progress_pct,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found in hierarchy")
    return {"status": "updated", "goal_id": goal_id, "new_status": status}


@router.post("/cognitive/goals/{goal_id}/milestones")
async def add_milestone(
    goal_id: str,
    name: str = Query(...),
    description: str = Query(""),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    milestone = engine.goal_memory.add_milestone(goal_id, name, description)
    if not milestone:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"milestone": milestone}


@router.post("/cognitive/goals/{goal_id}/milestones/{milestone_id}/complete")
async def complete_milestone(goal_id: str, milestone_id: str) -> Dict[str, Any]:
    engine = _get_cognitive()
    success = engine.goal_memory.complete_milestone(goal_id, milestone_id)
    if not success:
        raise HTTPException(status_code=404, detail="Goal or milestone not found")
    return {"status": "completed"}


@router.get("/cognitive/learning")
async def learning_summary() -> Dict[str, Any]:
    engine = _get_cognitive()
    return engine.adaptive_learning.get_summary()


@router.get("/cognitive/confidence")
async def confidence_stats() -> Dict[str, Any]:
    engine = _get_cognitive()
    return engine.confidence_v2.get_stats()


@router.post("/cognitive/confidence/evaluate")
async def evaluate_confidence(
    capability: str = Query(...),
    strategy: str = Query("direct"),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    score = engine.confidence_v2.score_pre_execution(
        capability=capability,
        candidate_agents=[],
        candidate_tools=[],
        strategy=strategy,
    )
    return {
        "capability": capability,
        "strategy": strategy,
        "overall_confidence": score.overall_confidence,
        "overall_risk": score.overall_risk,
        "warnings": score.warnings,
        "should_proceed": engine.confidence_v2.should_proceed(score),
    }


@router.get("/cognitive/reflections")
async def reflection_stats() -> Dict[str, Any]:
    engine = _get_cognitive()
    return engine.reflection_v2.get_stats()


@router.get("/cognitive/scheduler")
async def scheduler_stats() -> Dict[str, Any]:
    engine = _get_cognitive()
    return {
        "stats": engine.autonomous_scheduler.get_stats(),
        "pending": engine.autonomous_scheduler.get_pending(),
    }


@router.post("/cognitive/scheduler/schedule")
async def schedule_mission(
    objective: str = Query(...),
    delay_seconds: float = Query(0.0),
    priority: float = Query(5.0),
    recurring: bool = Query(False),
    interval_seconds: float = Query(0.0),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    orch = engine.get_or_create_orchestrator()
    return await orch.schedule_goal(
        objective=objective,
        delay_seconds=delay_seconds,
        priority=priority,
        recurring=recurring,
        interval_seconds=interval_seconds,
    )


@router.post("/cognitive/scheduler/start")
async def start_scheduler() -> Dict[str, Any]:
    engine = _get_cognitive()
    await engine.start_scheduler()
    return {"status": "started"}


@router.post("/cognitive/scheduler/stop")
async def stop_scheduler() -> Dict[str, Any]:
    engine = _get_cognitive()
    await engine.stop_scheduler()
    return {"status": "stopped"}


@router.post("/cognitive/scheduler/execute-due")
async def execute_due() -> Dict[str, Any]:
    engine = _get_cognitive()
    executed = await engine.autonomous_scheduler.execute_due()
    return {"executed": executed, "count": len(executed)}


@router.post("/cognitive/orchestrator/collaborate")
async def collaborative_workflow(
    objective: str = Query(...),
    description: str = Query(""),
    workflow_type: str = Query("research_code_review_test"),
    require_approval: bool = Query(False),
    use_mission_executor: bool = Query(False),
) -> Dict[str, Any]:
    engine = _get_cognitive()
    orch = engine.get_or_create_orchestrator()
    return await orch.collaborative_workflow(
        objective=objective,
        description=description,
        require_approval=require_approval,
        workflow_type=workflow_type,
        use_mission_executor=use_mission_executor,
    )


@router.post("/cognitive/consolidation/start")
async def start_consolidation() -> Dict[str, Any]:
    engine = _get_cognitive()
    await engine.start_consolidation()
    return {"status": "started"}


@router.post("/cognitive/consolidation/stop")
async def stop_consolidation() -> Dict[str, Any]:
    engine = _get_cognitive()
    await engine.stop_consolidation()
    return {"status": "stopped"}


@router.post("/cognitive/consolidation/run")
async def run_consolidation() -> Dict[str, Any]:
    engine = _get_cognitive()
    stats = await engine.run_consolidation()
    return stats
