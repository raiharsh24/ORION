from collections import defaultdict, deque
from typing import List, Dict, Set, Optional, Tuple

from app.planning.base import PlanStep


class ActionGraph:
    def __init__(self):
        self._nodes: Dict[str, PlanStep] = {}
        self._edges: Dict[str, List[str]] = defaultdict(list)
        self._reverse_edges: Dict[str, List[str]] = defaultdict(list)

    def add_step(self, step: PlanStep) -> str:
        self._nodes[step.step_id] = step
        return step.step_id

    def add_dependency(self, step_id: str, depends_on: str) -> None:
        if step_id not in self._nodes or depends_on not in self._nodes:
            return
        if depends_on not in self._edges[step_id]:
            self._edges[step_id].append(depends_on)
        if step_id not in self._reverse_edges[depends_on]:
            self._reverse_edges[depends_on].append(step_id)

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        return self._nodes.get(step_id)

    def get_dependencies(self, step_id: str) -> List[str]:
        return list(self._edges.get(step_id, []))

    def get_dependents(self, step_id: str) -> List[str]:
        return list(self._reverse_edges.get(step_id, []))

    @property
    def all_steps(self) -> List[PlanStep]:
        return list(self._nodes.values())

    @property
    def step_count(self) -> int:
        return len(self._nodes)

    def detect_cycles(self) -> List[List[str]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {sid: WHITE for sid in self._nodes}
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            dep = self._edges.get(node, [])
            for neighbor in dep:
                if neighbor not in self._nodes:
                    continue
                if color[neighbor] == GRAY:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for sid in self._nodes:
            if color[sid] == WHITE:
                dfs(sid)
        return cycles

    def has_cycles(self) -> bool:
        return len(self.detect_cycles()) > 0

    def topological_sort(self) -> List[PlanStep]:
        in_degree: Dict[str, int] = {sid: 0 for sid in self._nodes}
        for sid in self._nodes:
            for dep in self._edges.get(sid, []):
                if dep in in_degree:
                    in_degree[sid] = in_degree.get(sid, 0) + 1

        queue: deque = deque()
        for sid, degree in in_degree.items():
            if degree == 0:
                queue.append(sid)

        result: List[PlanStep] = []
        while queue:
            sid = queue.popleft()
            if sid in self._nodes:
                result.append(self._nodes[sid])
            for dependent in self._reverse_edges.get(sid, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        return result

    def get_parallel_batches(self) -> List[List[PlanStep]]:
        sorted_steps = self.topological_sort()
        if not sorted_steps:
            return []

        depth: Dict[str, int] = {}
        for step in sorted_steps:
            deps = self._edges.get(step.step_id, [])
            if not deps:
                depth[step.step_id] = 0
            else:
                max_dep_depth = max((depth.get(d, -1) for d in deps if d in self._nodes), default=-1)
                depth[step.step_id] = max_dep_depth + 1

        batches: Dict[int, List[PlanStep]] = defaultdict(list)
        for sid, d in depth.items():
            if sid in self._nodes:
                batches[d].append(self._nodes[sid])

        return [batches[i] for i in sorted(batches.keys())]

    def get_critical_path(self) -> List[PlanStep]:
        sorted_steps = self.topological_sort()
        if not sorted_steps:
            return []

        longest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for step in sorted_steps:
            sid = step.step_id
            deps = self._edges.get(sid, [])
            if not deps:
                longest[sid] = step.estimated_duration
                predecessor[sid] = None
            else:
                best_dep = max(
                    (d for d in deps if d in self._nodes),
                    key=lambda d: longest.get(d, 0) + step.estimated_duration,
                    default=None,
                )
                if best_dep:
                    longest[sid] = longest[best_dep] + step.estimated_duration
                    predecessor[sid] = best_dep
                else:
                    longest[sid] = step.estimated_duration
                    predecessor[sid] = None

        if not longest:
            return []

        max_sid = max(longest, key=longest.get)
        path: List[PlanStep] = []
        current = max_sid
        while current is not None:
            if current in self._nodes:
                path.append(self._nodes[current])
            current = predecessor.get(current)
        path.reverse()
        return path

    def dependency_depth(self, step_id: str) -> int:
        visited: Set[str] = set()

        def dfs(sid: str) -> int:
            if sid in visited or sid not in self._nodes:
                return 0
            visited.add(sid)
            deps = self._edges.get(sid, [])
            if not deps:
                return 0
            return 1 + max((dfs(d) for d in deps if d in self._nodes), default=0)

        return dfs(step_id)

    def get_max_depth(self) -> int:
        if not self._nodes:
            return 0
        return max(self.dependency_depth(sid) for sid in self._nodes)
