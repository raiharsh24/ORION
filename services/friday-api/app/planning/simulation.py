from dataclasses import dataclass, field
from typing import List, Dict, Any

from app.planning.base import Plan
from app.planning.graph import ActionGraph


@dataclass
class SimulationResult:
    estimated_runtime: float = 0.0
    estimated_resource_usage: float = 0.0
    success_probability: float = 1.0
    risk_score: float = 0.0
    bottlenecks: List[str] = field(default_factory=list)
    parallel_efficiency: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


class SimulationEngine:
    def simulate(self, plan: Plan) -> SimulationResult:
        graph = self._build_graph(plan)

        critical_path = graph.get_critical_path()
        runtime = sum(s.estimated_duration for s in critical_path)

        resource_usage = sum(s.estimated_cost for s in plan.steps)

        num_steps = len(plan.steps)
        if num_steps == 0:
            return SimulationResult()

        step_success_prob = 0.95
        success_prob = step_success_prob ** num_steps

        depth = graph.get_max_depth()
        risk_base = 1.0 - success_prob
        depth_risk = depth / max(num_steps, 1) * 0.2
        risk_score = min(1.0, risk_base + depth_risk)

        bottlenecks = self._identify_bottlenecks(plan, graph)

        batches = graph.get_parallel_batches()
        parallel_efficiency = 1.0
        if len(batches) > 1 and num_steps > 1:
            parallel_efficiency = min(1.0, num_steps / (len(batches) * 3.0))

        return SimulationResult(
            estimated_runtime=round(runtime, 2),
            estimated_resource_usage=round(resource_usage, 2),
            success_probability=round(success_prob, 4),
            risk_score=round(risk_score, 3),
            bottlenecks=bottlenecks,
            parallel_efficiency=round(parallel_efficiency, 3),
            details={
                "step_count": num_steps,
                "critical_path_length": len(critical_path),
                "max_depth": depth,
                "batch_count": len(batches),
                "step_success_rate": step_success_prob,
            },
        )

    def _build_graph(self, plan: Plan) -> ActionGraph:
        graph = ActionGraph()
        for step in plan.steps:
            graph.add_step(step)
        for step in plan.steps:
            for dep in step.dependencies:
                graph.add_dependency(step.step_id, dep)
        return graph

    def _identify_bottlenecks(self, plan: Plan,
                               graph: ActionGraph) -> List[str]:
        bottlenecks: List[str] = []

        deps_count: Dict[str, int] = {}
        for step in plan.steps:
            deps_count[step.step_id] = len(step.dependencies)

        max_deps = max(deps_count.values()) if deps_count else 0
        for sid, count in deps_count.items():
            if count > 0 and count == max_deps:
                step = graph.get_step(sid)
                if step:
                    bottlenecks.append(
                        f"Step '{step.action_name or sid}' has {count} dependencies"
                    )

        critical_path = graph.get_critical_path()
        if critical_path:
            longest = max(critical_path, key=lambda s: s.estimated_duration)
            if longest.estimated_duration > 0:
                bottlenecks.append(
                    f"Longest step on critical path: '{longest.action_name or longest.step_id}' "
                    f"({longest.estimated_duration:.1f}s)"
                )

        return bottlenecks
