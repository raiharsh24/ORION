from typing import Dict, List, Optional, Set, Tuple
from collections import deque

from app.workflow_engine.base import WorkflowGraph, WorkflowNode, WorkflowEdge, WorkflowNodeType


class WorkflowGraphBuilder:
    @staticmethod
    def build(nodes: List[WorkflowNode],
              edges: List[WorkflowEdge]) -> WorkflowGraph:
        graph = WorkflowGraph()
        for node in nodes:
            graph.add_node(node)
        for edge in edges:
            graph.add_edge(edge.source_id, edge.target_id)
        graph.entry_node_ids = WorkflowGraphBuilder._find_entry_nodes(graph)
        return graph

    @staticmethod
    def _find_entry_nodes(graph: WorkflowGraph) -> List[str]:
        has_incoming = set()
        for edge in graph.edges:
            has_incoming.add(edge.target_id)
        return [nid for nid in graph.nodes if nid not in has_incoming]

    @staticmethod
    def topological_sort(graph: WorkflowGraph) -> List[List[str]]:
        in_degree: Dict[str, int] = {nid: 0 for nid in graph.nodes}
        adjacency: Dict[str, List[str]] = {nid: [] for nid in graph.nodes}

        for edge in graph.edges:
            if edge.source_id in adjacency and edge.target_id in in_degree:
                adjacency[edge.source_id].append(edge.target_id)
                in_degree[edge.target_id] = in_degree.get(edge.target_id, 0) + 1

        layers: List[List[str]] = []
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])

        while queue:
            layer = list(queue)
            layers.append(layer)
            next_queue = deque()
            for nid in layer:
                for child in adjacency.get(nid, []):
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        next_queue.append(child)
            queue = next_queue

        return layers


class WorkflowValidator:
    @staticmethod
    def validate(graph: WorkflowGraph) -> List[str]:
        errors = []

        for nid, node in graph.nodes.items():
            if node.node_type == WorkflowNodeType.TOOL and not node.tool_id:
                errors.append(f"Node '{nid}' is TOOL type but has no tool_id")

        edges_map: Dict[str, List[str]] = {}
        for edge in graph.edges:
            edges_map.setdefault(edge.source_id, []).append(edge.target_id)

        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(nid: str) -> bool:
            visited.add(nid)
            stack.add(nid)
            for child in edges_map.get(nid, []):
                if child not in visited:
                    if dfs(child):
                        return True
                elif child in stack:
                    errors.append(f"Cycle detected: {nid} -> {child}")
                    return True
            stack.discard(nid)
            return False

        for nid in graph.nodes:
            if nid not in visited:
                dfs(nid)

        return errors
