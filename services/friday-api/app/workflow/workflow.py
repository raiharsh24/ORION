"""
Workflow domain models — core data structures for FRIDAY Workflow Engine.

Supports: Sequential, Parallel, Conditional, Loop, Delay, Retry, Approval,
Failure-routing, and Completion-routing node flow types.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class WorkflowNodeStatus(str, Enum):
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED   = "SKIPPED"
    PAUSED    = "PAUSED"
    WAITING   = "WAITING"     # Waiting for approval or delay
    RETRYING  = "RETRYING"


class WorkflowNodeType(str, Enum):
    DESKTOP_ACTION  = "Desktop Action"
    MISSION         = "Mission"
    LLM_PROMPT      = "LLM Prompt"
    KNOWLEDGE_QUERY = "Knowledge Query"
    PLANNER_STEP    = "Planner Step"
    CONDITION       = "Condition"
    DELAY           = "Delay"
    NOTIFICATION    = "Notification"


class WorkflowFlowType(str, Enum):
    """Controls how a node fans out to successors."""
    SEQUENTIAL   = "SEQUENTIAL"    # One at a time, in depends_on order
    PARALLEL     = "PARALLEL"      # All dependencies fire simultaneously
    CONDITIONAL  = "CONDITIONAL"   # Route via on_success / on_failure edges
    LOOP         = "LOOP"          # Repeat node up to loop_count times
    DELAY        = "DELAY"         # Wait before executing
    RETRY        = "RETRY"         # Retry on failure up to max_retries
    APPROVAL     = "APPROVAL"      # Pause and wait for human sign-off
    FAILURE      = "FAILURE"       # Explicit failure terminal
    COMPLETION   = "COMPLETION"    # Explicit success terminal


class ConditionConfig(BaseModel):
    """Inline condition config for CONDITION nodes."""
    type: str = "expression"          # expression | status_check | comparison | boolean | mission_status | desktop_status
    params: Dict[str, Any] = Field(default_factory=dict)
    on_true: Optional[str] = None     # node_id to jump to when true
    on_false: Optional[str] = None    # node_id to jump to when false


class WorkflowNode(BaseModel):
    id: str
    name: str
    type: str  # WorkflowNodeType value or custom string
    status: WorkflowNodeStatus = WorkflowNodeStatus.PENDING
    flow_type: WorkflowFlowType = WorkflowFlowType.SEQUENTIAL

    # Graph topology
    depends_on: List[str] = Field(default_factory=list)
    on_success: Optional[str] = None   # next node_id on success
    on_failure: Optional[str] = None   # next node_id on failure

    # Execution config
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)

    # Retry / loop config
    retry_count: int = 0
    max_retries: int = 0
    loop_count: int = 0
    loop_max: int = 1
    delay_seconds: float = 0.0

    # Condition config (for CONDITION node type)
    condition: Optional[ConditionConfig] = None

    # Tracking
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStatus(str, Enum):
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    PAUSED    = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    CANCELLED = "CANCELLED"


class Workflow(BaseModel):
    id: str
    name: str
    description: str
    flow_type: WorkflowFlowType = WorkflowFlowType.SEQUENTIAL
    template_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    timeout_seconds: Optional[float] = None
    max_retries: int = 0

    nodes: Dict[str, WorkflowNode] = Field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING

    # Runtime variables namespace
    variables: Dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
