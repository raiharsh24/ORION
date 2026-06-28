"""
Workflow graph traversal utilities.

Provides:
- Cycle detection (DFS)
- Topological sort
- Downstream status propagation
- Runnable node resolution (parallel-aware)
- Parallel fan-out group detection
- Conditional next-node routing via on_success / on_failure edges
"""
from typing import List, Dict, Set, Any, Optional
from app.workflow.workflow import Workflow, WorkflowNode, WorkflowNodeStatus


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def has_cycle(nodes: Dict[str, WorkflowNode]) -> bool:
    """Checks if the workflow graph contains any cycles using DFS."""
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def dfs(node_id: str) -> bool:
        visited.add(node_id)
        rec_stack.add(node_id)
        node = nodes.get(node_id)
        if node:
            for dep_id in node.depends_on:
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
        rec_stack.remove(node_id)
        return False

    for node_id in nodes:
        if node_id not in visited:
            if dfs(node_id):
                return True
    return False


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def topological_sort(nodes: Dict[str, WorkflowNode]) -> List[str]:
    """
    Returns a topologically sorted list of node IDs.
    Returns empty list if a cycle is detected.
    """
    if has_cycle(nodes):
        return []

    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node_id: str) -> None:
        visited.add(node_id)
        node = nodes.get(node_id)
        if node:
            for dep_id in node.depends_on:
                if dep_id not in visited:
                    dfs(dep_id)
        stack.append(node_id)

    for node_id in nodes:
        if node_id not in visited:
            dfs(node_id)

    return stack


# ---------------------------------------------------------------------------
# Downstream status propagation
# ---------------------------------------------------------------------------

def propagate_statuses(workflow: Workflow) -> None:
    """
    Propagates failure/cancellation/skip statuses down the graph.
    If a node depends on a failed, cancelled, or skipped node it becomes CANCELLED.
    """
    order = topological_sort(workflow.nodes)
    for node_id in order:
        node = workflow.nodes[node_id]
        if node.status != WorkflowNodeStatus.PENDING:
            continue
        for dep_id in node.depends_on:
            dep_node = workflow.nodes.get(dep_id)
            if dep_node and dep_node.status in [
                WorkflowNodeStatus.FAILED,
                WorkflowNodeStatus.CANCELLED,
                WorkflowNodeStatus.SKIPPED,
            ]:
                node.status = WorkflowNodeStatus.CANCELLED
                node.error = (
                    f"Upstream dependency node '{dep_id}' "
                    f"was {dep_node.status.value.lower()}."
                )
                break


# ---------------------------------------------------------------------------
# Runnable node resolution
# ---------------------------------------------------------------------------

def get_runnable_nodes(workflow: Workflow) -> List[WorkflowNode]:
    """
    Resolves which nodes are currently PENDING and have all dependencies COMPLETED.
    Before returning, propagates skipped / cancelled states downstream.
    """
    propagate_statuses(workflow)

    runnable = []
    for node in workflow.nodes.values():
        if node.status != WorkflowNodeStatus.PENDING:
            continue
        deps_met = all(
            workflow.nodes.get(dep_id) and
            workflow.nodes[dep_id].status == WorkflowNodeStatus.COMPLETED
            for dep_id in node.depends_on
        )
        if deps_met:
            runnable.append(node)

    return runnable


# ---------------------------------------------------------------------------
# Parallel group detection
# ---------------------------------------------------------------------------

def get_parallel_groups(workflow: Workflow) -> List[List[str]]:
    """
    Groups runnable nodes by their dependency sets so that nodes sharing the
    same dependencies can be dispatched simultaneously.

    Returns a list of groups; each group is a list of node_ids that can run
    in parallel with each other.
    """
    runnable = get_runnable_nodes(workflow)

    # Group nodes that share the same frozen dependency set
    dep_groups: Dict[frozenset, List[str]] = {}
    for node in runnable:
        key = frozenset(node.depends_on)
        dep_groups.setdefault(key, []).append(node.id)

    return list(dep_groups.values())


# ---------------------------------------------------------------------------
# Conditional next-node routing
# ---------------------------------------------------------------------------

def get_next_node(
    node: WorkflowNode,
    success: bool,
    workflow: Workflow
) -> Optional[WorkflowNode]:
    """
    Resolves the next node to execute after a conditional node completes.

    For CONDITION / CONDITIONAL-flow nodes, follows on_success / on_failure
    edge labels.  For all other nodes falls back to standard dependency
    resolution via get_runnable_nodes.

    Args:
        node:    The node that just completed.
        success: True if the node completed successfully (or condition was True).
        workflow: The live workflow instance.

    Returns:
        The next WorkflowNode to execute, or None if execution should stop.
    """
    target_id: Optional[str] = node.on_success if success else node.on_failure
    if target_id:
        return workflow.nodes.get(target_id)
    return None
