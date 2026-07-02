from typing import Dict, Any, List, Optional, Callable

from app.tool_selection.base import ToolSelectionResult, SelectedTool
from app.tools.base import ToolDefinition
from app.workflow_engine.base import (
    WorkflowGraph, WorkflowNode, WorkflowEdge, WorkflowNodeType,
)
from app.workflow_engine.graph import WorkflowGraphBuilder


class WorkflowPlanner:
    @staticmethod
    def plan_from_selection(
        selection: ToolSelectionResult,
        edges: Optional[List[WorkflowEdge]] = None,
        args_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> WorkflowGraph:
        nodes: List[WorkflowNode] = []
        for st in selection.selected_tools:
            tid = st.tool.id
            nodes.append(WorkflowNode(
                id=tid,
                name=st.tool.name,
                node_type=WorkflowNodeType.TOOL,
                tool_id=tid,
                args=dict(args_overrides.get(tid, {})) if args_overrides else {},
                timeout=max(30.0, st.tool.estimated_latency_ms / 1000.0 + 5.0),
            ))

        all_edges = list(edges or [])
        return WorkflowGraphBuilder.build(nodes, all_edges)
