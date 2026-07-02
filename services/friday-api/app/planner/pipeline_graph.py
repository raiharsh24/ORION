from typing import Set, Dict, List

class PipelineGraph:
    def __init__(self) -> None:
        self.nodes: Set[str] = set()
        self.edges: Dict[str, Set[str]] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self._global_order = [
            "intent",
            "strategy",
            "extraction",
            "ranking",
            "budget",
            "incremental_update",
            "validation",
            "compression",
            "assembly",
        ]

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        if node not in self._global_order:
            self._global_order.append(node)

    def add_edge(self, u: str, v: str) -> None:
        self.add_node(u)
        self.add_node(v)
        if u not in self.edges:
            self.edges[u] = set()
        if v not in self.dependencies:
            self.dependencies[v] = set()
        self.edges[u].add(v)
        self.dependencies[v].add(u)
        
        # Adjust global order to satisfy u -> v
        u_idx = self._global_order.index(u)
        v_idx = self._global_order.index(v)
        if v_idx < u_idx:
            self._global_order.remove(v)
            self._global_order.insert(u_idx, v)

    def get_stages_ordered(self, enabled_stages: Set[str]) -> List[str]:
        return [node for node in self._global_order if node in enabled_stages]
