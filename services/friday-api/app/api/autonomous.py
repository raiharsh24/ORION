from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List

from app.autonomous_dev.manager import AutonomousDevelopmentManager
from app.autonomous_dev.models import AutonomousGoal, AutonomousTask

router = APIRouter()

def get_autonomous_manager() -> AutonomousDevelopmentManager:
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    manager = kernel.get_service("autonomous_manager")
    if not manager:
        raise HTTPException(status_code=503, detail="AutonomousDevelopmentManager is not available.")
    return manager

@router.post("/autonomous/start", response_model=AutonomousGoal)
async def start_autonomous_session(
    prompt: str,
    manager: AutonomousDevelopmentManager = Depends(get_autonomous_manager)
):
    """
    Starts a new autonomous goal.
    """
    try:
        goal = await manager.start_autonomous_goal(prompt=prompt)
        return goal
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/autonomous/stop")
async def stop_autonomous_session(
    goal_id: str,
    manager: AutonomousDevelopmentManager = Depends(get_autonomous_manager)
):
    """
    Stops a running autonomous goal.
    """
    try:
        await manager.stop_autonomous_goal(goal_id=goal_id)
        return {"message": f"Goal {goal_id} stopped."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/autonomous/status", response_model=AutonomousGoal)
async def get_autonomous_status(
    goal_id: str,
    manager: AutonomousDevelopmentManager = Depends(get_autonomous_manager)
):
    """
    Gets the status of a specific goal.
    """
    goal = manager.get_goal_status(goal_id=goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return goal

@router.get("/autonomous/goals", response_model=List[AutonomousGoal])
async def get_all_goals(
    manager: AutonomousDevelopmentManager = Depends(get_autonomous_manager)
):
    """
    Gets all autonomous goals.
    """
    return manager.get_all_goals()

@router.get("/autonomous/tasks", response_model=List[AutonomousTask])
async def get_autonomous_tasks(
    goal_id: str,
    manager: AutonomousDevelopmentManager = Depends(get_autonomous_manager)
):
    """
    Gets all tasks for a specific goal.
    """
    tasks = manager.get_tasks_for_goal(goal_id=goal_id)
    return tasks

# Placeholder for WebSocket events endpoint
@router.websocket("/autonomous/events")
async def autonomous_events(websocket: WebSocket):
    await websocket.accept()
    # This will be implemented to stream events from the EventBus
    await websocket.send_text("Connected to autonomous events stream.")
    # Keep connection open
    while True:
        try:
            await websocket.receive_text()
        except WebSocketDisconnect:
            break
