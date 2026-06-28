"""
Workflow Engine API Routes.

Provides REST endpoints for:
  - Listing / creating workflows
  - Workflow lifecycle: start, pause, resume, cancel, restart
  - Node-level retry
  - Execution history
  - Built-in template listing
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.kernel.kernel import FridayKernel
from app.workflow.workflow import Workflow, WorkflowNode, WorkflowFlowType, WorkflowStatus, WorkflowNodeStatus, ConditionConfig
from app.workflow.engine import WorkflowEngine
from app.workflow.templates import list_templates, build_workflow_from_template

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_engine() -> WorkflowEngine:
    kernel = FridayKernel.get_instance()
    engine = kernel.get_service("workflow_engine")
    if not engine:
        raise HTTPException(status_code=500, detail="Workflow Engine not registered in Kernel.")
    return engine


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ConditionConfigRequest(BaseModel):
    type: str = "boolean"
    params: Dict[str, Any] = {}
    on_true: Optional[str] = None
    on_false: Optional[str] = None


class WorkflowNodeRequest(BaseModel):
    id: str
    name: str
    type: str
    flow_type: str = "SEQUENTIAL"
    depends_on: List[str] = []
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    inputs: Dict[str, Any] = {}
    max_retries: int = 0
    delay_seconds: float = 0.0
    loop_max: int = 1
    condition: Optional[ConditionConfigRequest] = None
    metadata: Dict[str, Any] = {}


class CreateWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    flow_type: str = "SEQUENTIAL"
    template_id: Optional[str] = None
    tags: List[str] = []
    timeout_seconds: Optional[float] = None
    max_retries: int = 0
    nodes: List[WorkflowNodeRequest] = []
    variables: Dict[str, Any] = {}


class WorkflowNodeResponse(BaseModel):
    id: str
    name: str
    type: str
    status: str
    flow_type: str
    depends_on: List[str]
    on_success: Optional[str]
    on_failure: Optional[str]
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    error: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    retry_count: int
    loop_count: int
    metadata: Dict[str, Any]


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    flow_type: str
    template_id: Optional[str]
    tags: List[str]
    nodes: Dict[str, WorkflowNodeResponse]
    variables: Dict[str, Any]
    created_at: str
    updated_at: str
    error: Optional[str]
    metadata: Dict[str, Any]


class WorkflowRunResponse(BaseModel):
    run_id: str
    workflow_id: str
    workflow_name: str
    status: str
    current_node_id: Optional[str]
    completed_nodes: List[str]
    failed_nodes: List[str]
    total_retries: int
    duration_seconds: float
    error: Optional[str]
    branch_decisions: List[Dict[str, Any]]


class WorkflowActionResponse(BaseModel):
    success: bool
    workflow_id: str
    message: str
    run_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_to_response(node: WorkflowNode) -> WorkflowNodeResponse:
    return WorkflowNodeResponse(
        id=node.id,
        name=node.name,
        type=node.type,
        status=node.status.value,
        flow_type=node.flow_type.value,
        depends_on=node.depends_on,
        on_success=node.on_success,
        on_failure=node.on_failure,
        inputs=node.inputs,
        outputs=node.outputs,
        error=node.error,
        started_at=node.started_at,
        finished_at=node.finished_at,
        retry_count=node.retry_count,
        loop_count=node.loop_count,
        metadata=node.metadata,
    )


def _workflow_to_response(wf: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=wf.id,
        name=wf.name,
        description=wf.description,
        status=wf.status.value,
        flow_type=wf.flow_type.value,
        template_id=wf.template_id,
        tags=wf.tags,
        nodes={nid: _node_to_response(n) for nid, n in wf.nodes.items()},
        variables=wf.variables,
        created_at=wf.created_at.isoformat(),
        updated_at=wf.updated_at.isoformat(),
        error=wf.error,
        metadata=wf.metadata,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/workflows", response_model=List[WorkflowResponse])
async def list_workflows() -> List[WorkflowResponse]:
    """List all registered workflows with current execution status."""
    engine = get_engine()
    return [_workflow_to_response(wf) for wf in engine.list_workflows()]


@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(request: CreateWorkflowRequest) -> WorkflowResponse:
    """
    Create a new workflow from a node definition or from a built-in template.
    If template_id is provided, nodes are generated from the template.
    """
    engine = get_engine()

    if request.template_id:
        workflow = build_workflow_from_template(
            request.template_id,
            overrides={
                "name": request.name,
                "description": request.description,
                "variables": request.variables,
            }
        )
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{request.template_id}' not found."
            )
    else:
        # Build from supplied node definitions
        try:
            flow_type = WorkflowFlowType(request.flow_type)
        except ValueError:
            flow_type = WorkflowFlowType.SEQUENTIAL

        nodes: Dict[str, WorkflowNode] = {}
        for nr in request.nodes:
            try:
                node_flow = WorkflowFlowType(nr.flow_type)
            except ValueError:
                node_flow = WorkflowFlowType.SEQUENTIAL

            cond = None
            if nr.condition:
                cond = ConditionConfig(
                    type=nr.condition.type,
                    params=nr.condition.params,
                    on_true=nr.condition.on_true,
                    on_false=nr.condition.on_false,
                )
            node = WorkflowNode(
                id=nr.id,
                name=nr.name,
                type=nr.type,
                flow_type=node_flow,
                depends_on=nr.depends_on,
                on_success=nr.on_success,
                on_failure=nr.on_failure,
                inputs=nr.inputs,
                max_retries=nr.max_retries,
                delay_seconds=nr.delay_seconds,
                loop_max=nr.loop_max,
                condition=cond,
                metadata=nr.metadata,
            )
            nodes[node.id] = node

        workflow = Workflow(
            id=uuid.uuid4().hex,
            name=request.name,
            description=request.description,
            flow_type=flow_type,
            tags=request.tags,
            timeout_seconds=request.timeout_seconds,
            max_retries=request.max_retries,
            nodes=nodes,
            variables=request.variables,
        )

    registered = engine.create_workflow(workflow)
    return _workflow_to_response(registered)


@router.get("/workflows/templates")
async def get_templates() -> List[Dict[str, Any]]:
    """List all built-in workflow templates."""
    return list_templates()


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str) -> WorkflowResponse:
    """Get a workflow by ID including current node states."""
    engine = get_engine()
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
    return _workflow_to_response(wf)


@router.post("/workflows/{workflow_id}/start", response_model=WorkflowActionResponse)
async def start_workflow(workflow_id: str) -> WorkflowActionResponse:
    """Start workflow execution. Returns the new run_id."""
    engine = get_engine()
    run_id = await engine.start(workflow_id)
    if not run_id:
        raise HTTPException(
            status_code=400,
            detail=f"Could not start workflow '{workflow_id}'. Check it exists and is not already running."
        )
    return WorkflowActionResponse(
        success=True,
        workflow_id=workflow_id,
        message="Workflow started.",
        run_id=run_id,
    )


@router.post("/workflows/{workflow_id}/pause", response_model=WorkflowActionResponse)
async def pause_workflow(workflow_id: str) -> WorkflowActionResponse:
    """Pause a running workflow at the next safe checkpoint."""
    engine = get_engine()
    ok = await engine.pause(workflow_id)
    return WorkflowActionResponse(
        success=ok,
        workflow_id=workflow_id,
        message="Workflow paused." if ok else "No active workflow to pause.",
    )


@router.post("/workflows/{workflow_id}/resume", response_model=WorkflowActionResponse)
async def resume_workflow(workflow_id: str) -> WorkflowActionResponse:
    """Resume a paused workflow."""
    engine = get_engine()
    ok = await engine.resume(workflow_id)
    return WorkflowActionResponse(
        success=ok,
        workflow_id=workflow_id,
        message="Workflow resumed." if ok else "No paused workflow to resume.",
    )


@router.post("/workflows/{workflow_id}/cancel", response_model=WorkflowActionResponse)
async def cancel_workflow(workflow_id: str) -> WorkflowActionResponse:
    """Cancel an active workflow execution."""
    engine = get_engine()
    ok = await engine.cancel(workflow_id)
    return WorkflowActionResponse(
        success=ok,
        workflow_id=workflow_id,
        message="Workflow cancelled." if ok else "No active workflow to cancel.",
    )


@router.post("/workflows/{workflow_id}/restart", response_model=WorkflowActionResponse)
async def restart_workflow(workflow_id: str) -> WorkflowActionResponse:
    """Cancel the current run and start a fresh one."""
    engine = get_engine()
    run_id = await engine.restart(workflow_id)
    if not run_id:
        raise HTTPException(
            status_code=400,
            detail=f"Could not restart workflow '{workflow_id}'."
        )
    return WorkflowActionResponse(
        success=True,
        workflow_id=workflow_id,
        message="Workflow restarted.",
        run_id=run_id,
    )


@router.post("/workflows/{workflow_id}/retry/{node_id}", response_model=WorkflowActionResponse)
async def retry_node(workflow_id: str, node_id: str) -> WorkflowActionResponse:
    """Reset a failed node to PENDING so it will be retried."""
    engine = get_engine()
    ok = await engine.retry_node(workflow_id, node_id)
    return WorkflowActionResponse(
        success=ok,
        workflow_id=workflow_id,
        message=f"Node '{node_id}' reset for retry." if ok else f"Could not retry node '{node_id}'.",
    )


@router.get("/workflows/{workflow_id}/history", response_model=List[WorkflowRunResponse])
async def get_workflow_history(workflow_id: str) -> List[WorkflowRunResponse]:
    """Get all execution run records for a workflow."""
    engine = get_engine()
    history = engine._history
    runs = history.list_by_workflow(workflow_id)

    def _run_to_response(run) -> WorkflowRunResponse:
        return WorkflowRunResponse(
            run_id=run.run_id,
            workflow_id=run.workflow_id,
            workflow_name=run.workflow_name,
            status=run.status.value,
            current_node_id=run.current_node_id,
            completed_nodes=run.completed_nodes,
            failed_nodes=run.failed_nodes,
            total_retries=run.total_retries,
            duration_seconds=run.elapsed_seconds(),
            error=run.error,
            branch_decisions=[
                {
                    "node_id":          bd.node_id,
                    "condition_result":  bd.condition_result,
                    "branch_taken":      bd.branch_taken,
                    "next_node_id":      bd.next_node_id,
                    "timestamp":         bd.timestamp,
                }
                for bd in run.branch_decisions
            ]
        )

    return [_run_to_response(r) for r in runs]


@router.get("/workflows/active", response_model=List[Dict[str, Any]])
async def get_active_workflows() -> List[Dict[str, Any]]:
    """Returns all currently running workflow summaries (for Kernel telemetry)."""
    engine = get_engine()
    return engine.get_active_workflows()
