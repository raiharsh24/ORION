from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone


class WorkflowNodeType(str, Enum):
    TOOL = "tool"
    CONDITION = "condition"
    PARALLEL = "parallel"
    MERGE = "merge"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    id: str
    name: str = ""
    node_type: WorkflowNodeType = WorkflowNodeType.TOOL
    tool_id: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 60.0
    max_retries: int = 0
    retry_delay: float = 1.0
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    parallel_branches: Optional[List[List[str]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowEdge:
    source_id: str
    target_id: str
    data: Optional[Any] = None


@dataclass
class ExecutedNode:
    node_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    retries: int = 0
    branch_taken: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status == WorkflowStatus.COMPLETED


@dataclass
class WorkflowGraph:
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    edges: List[WorkflowEdge] = field(default_factory=list)
    entry_node_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, source_id: str, target_id: str) -> None:
        self.edges.append(WorkflowEdge(source_id=source_id, target_id=target_id))

    def get_children(self, node_id: str) -> List[str]:
        return [e.target_id for e in self.edges if e.source_id == node_id]

    def get_parents(self, node_id: str) -> List[str]:
        return [e.source_id for e in self.edges if e.target_id == node_id]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


@dataclass
class WorkflowContext:
    execution_id: str = ""
    shared_data: Dict[str, Any] = field(default_factory=dict)
    node_outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class WorkflowExecutionResult:
    execution_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    node_results: Dict[str, ExecutedNode] = field(default_factory=dict)
    context: Optional[WorkflowContext] = None
    total_duration_ms: float = 0.0
    critical_path_ms: float = 0.0
    parallelism: float = 0.0
    error: Optional[str] = None
    failed_node_id: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    branch_decisions: Dict[str, str] = field(default_factory=dict)
