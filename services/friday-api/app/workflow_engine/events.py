from typing import Dict, Any, Optional
from app.events.events import FridayEvent


class WorkflowStarted(FridayEvent):
    def __init__(self, execution_id: str = "", graph_id: str = "",
                 total_nodes: int = 0) -> None:
        super().__init__(topic="WorkflowStarted", data={
            "execution_id": execution_id,
            "graph_id": graph_id,
            "total_nodes": total_nodes,
        })


class WorkflowNodeStarted(FridayEvent):
    def __init__(self, execution_id: str = "", node_id: str = "",
                 node_type: str = "", tool_id: str = "") -> None:
        super().__init__(topic="WorkflowNodeStarted", data={
            "execution_id": execution_id,
            "node_id": node_id,
            "node_type": node_type,
            "tool_id": tool_id,
        })


class WorkflowNodeCompleted(FridayEvent):
    def __init__(self, execution_id: str = "", node_id: str = "",
                 status: str = "", duration_ms: float = 0.0) -> None:
        super().__init__(topic="WorkflowNodeCompleted", data={
            "execution_id": execution_id,
            "node_id": node_id,
            "status": status,
            "duration_ms": duration_ms,
        })


class WorkflowCompleted(FridayEvent):
    def __init__(self, execution_id: str = "", status: str = "",
                 total_duration_ms: float = 0.0,
                 total_nodes: int = 0) -> None:
        super().__init__(topic="WorkflowCompleted", data={
            "execution_id": execution_id,
            "status": status,
            "total_duration_ms": total_duration_ms,
            "total_nodes": total_nodes,
        })


class WorkflowFailed(FridayEvent):
    def __init__(self, execution_id: str = "", node_id: str = "",
                 error: str = "") -> None:
        super().__init__(topic="WorkflowFailed", data={
            "execution_id": execution_id,
            "node_id": node_id,
            "error": error,
        })


class WorkflowCancelled(FridayEvent):
    def __init__(self, execution_id: str = "", reason: str = "") -> None:
        super().__init__(topic="WorkflowCancelled", data={
            "execution_id": execution_id,
            "reason": reason,
        })
