import math
from dataclasses import dataclass

from app.planning.base import Plan
from app.planning.graph import ActionGraph


@dataclass
class HeuristicScores:
    complexity: float = 0.0
    cost: float = 0.0
    latency: float = 0.0
    parallelism: float = 0.0
    dependency_depth: float = 0.0
    risk: float = 0.0
    total: float = 0.0


class HeuristicScorer:
    def score(self, plan: Plan) -> HeuristicScores:
        graph = self._build_graph(plan)
        complexity = self._score_complexity(plan, graph)
        cost = self._score_cost(plan)
        latency = self._score_latency(plan, graph)
        parallelism = self._score_parallelism(plan, graph)
        dep_depth = self._score_dependency_depth(plan, graph)
        risk = self._score_risk(plan, graph)

        normalized_total = (
            self._normalize(complexity, 0, 100) * 0.15
            + self._normalize(cost, 0, 100) * 0.20
            + self._normalize(latency, 0, 100) * 0.15
            + parallelism * 0.15
            + self._normalize(dep_depth, 0, 20) * 0.10
            + (1.0 - self._normalize(risk, 0, 100)) * 0.25
        )
        normalized_total = max(0.0, min(1.0, normalized_total))

        return HeuristicScores(
            complexity=round(complexity, 3),
            cost=round(cost, 3),
            latency=round(latency, 3),
            parallelism=round(parallelism, 3),
            dependency_depth=round(dep_depth, 3),
            risk=round(risk, 3),
            total=round(normalized_total, 3),
        )

    def _build_graph(self, plan: Plan) -> ActionGraph:
        graph = ActionGraph()
        for step in plan.steps:
            graph.add_step(step)
        for step in plan.steps:
            for dep in step.dependencies:
                graph.add_dependency(step.step_id, dep)
        return graph

    def _score_complexity(self, plan: Plan, graph: ActionGraph) -> float:
        step_count = len(plan.steps)
        edge_count = sum(len(s.dependencies) for s in plan.steps)
        return float(step_count + edge_count)

    def _score_cost(self, plan: Plan) -> float:
        return sum(s.estimated_cost for s in plan.steps)

    def _score_latency(self, plan: Plan, graph: ActionGraph) -> float:
        critical_path = graph.get_critical_path()
        return sum(s.estimated_duration for s in critical_path)

    def _score_parallelism(self, plan: Plan, graph: ActionGraph) -> float:
        if len(plan.steps) <= 1:
            return 1.0
        batches = graph.get_parallel_batches()
        if not batches:
            return 1.0
        return max(0.0, min(1.0, len(plan.steps) / (len(batches) * 2)))

    def _score_dependency_depth(self, plan: Plan, graph: ActionGraph) -> float:
        return float(graph.get_max_depth())

    def _score_risk(self, plan: Plan, graph: ActionGraph) -> float:
        num_steps = len(plan.steps)
        if num_steps == 0:
            return 0.0
        failure_prob = 1.0 - (0.95 ** num_steps)
        depth_penalty = graph.get_max_depth() / max(num_steps, 1) * 0.1
        cost_factor = min(1.0, sum(s.estimated_cost for s in plan.steps) / 100.0)
        return round((failure_prob + depth_penalty + cost_factor * 0.1) / 2.1, 3)

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        if max_val <= min_val:
            return 1.0
        clamped = max(min_val, min(max_val, value))
        return (clamped - min_val) / (max_val - min_val)
