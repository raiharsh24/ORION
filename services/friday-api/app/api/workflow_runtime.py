from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState
from app.workflow_runtime.models import ExecutionPlanInput, RuntimeWorkflow, WorkflowSummary

router = APIRouter()

class PlanSubmitRequest(BaseModel):
    plan_id: str
    goal: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class StepRetryRequest(BaseModel):
    step_id: str

class RecoverResponse(BaseModel):
    recovered_count: int

async def _get_bridge():
    kernel = FridayKernel.get_instance()
    if kernel.state() == KernelState.STOPPED:
        await kernel.boot()
    bridge = kernel.get_service("runtime_scheduler_bridge")
    if not bridge:
        raise HTTPException(status_code=503, detail="Runtime scheduler bridge not available")
    return bridge

@router.post("/runtime/plans", response_model=Dict[str, str])
async def submit_plan(request: PlanSubmitRequest) -> Dict[str, str]:
    bridge = await _get_bridge()
    plan = ExecutionPlanInput(**request.model_dump())
    workflow_id = await bridge.submit_plan(plan)
    return {"workflow_id": workflow_id}

@router.get("/runtime/workflows", response_model=List[RuntimeWorkflow])
async def list_all_workflows() -> List[RuntimeWorkflow]:
    bridge = await _get_bridge()
    return await bridge.list_all()

@router.get("/runtime/workflows/active", response_model=List[RuntimeWorkflow])
async def list_active_workflows() -> List[RuntimeWorkflow]:
    bridge = await _get_bridge()
    return bridge.list_active()

@router.get("/runtime/workflows/summaries", response_model=List[WorkflowSummary])
async def list_workflow_summaries() -> List[WorkflowSummary]:
    bridge = await _get_bridge()
    summaries = await bridge.list_summaries()
    return [WorkflowSummary(**s) if isinstance(s, dict) else s for s in summaries]

@router.get("/runtime/workflows/{workflow_id}", response_model=RuntimeWorkflow)
async def get_workflow(workflow_id: str) -> RuntimeWorkflow:
    bridge = await _get_bridge()
    wf = bridge.get(workflow_id)
    if not wf:
        wf = await bridge.get_stored(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return wf

@router.post("/runtime/workflows/{workflow_id}/pause", response_model=Dict[str, bool])
async def pause_workflow(workflow_id: str) -> Dict[str, bool]:
    bridge = await _get_bridge()
    result = await bridge.pause(workflow_id)
    return {"success": result}

@router.post("/runtime/workflows/{workflow_id}/resume", response_model=Dict[str, bool])
async def resume_workflow(workflow_id: str) -> Dict[str, bool]:
    bridge = await _get_bridge()
    result = await bridge.resume(workflow_id)
    return {"success": result}

@router.post("/runtime/workflows/{workflow_id}/cancel", response_model=Dict[str, bool])
async def cancel_workflow(workflow_id: str) -> Dict[str, bool]:
    bridge = await _get_bridge()
    result = await bridge.cancel(workflow_id)
    return {"success": result}

@router.post("/runtime/workflows/{workflow_id}/retry", response_model=Dict[str, bool])
async def retry_workflow_step(workflow_id: str, request: StepRetryRequest) -> Dict[str, bool]:
    bridge = await _get_bridge()
    result = await bridge.retry_step(workflow_id, request.step_id)
    return {"success": result}

@router.post("/runtime/recover", response_model=RecoverResponse)
async def recover_workflows() -> RecoverResponse:
    bridge = await _get_bridge()
    count = await bridge.recover()
    return RecoverResponse(recovered_count=count)
