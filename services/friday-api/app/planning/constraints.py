from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set

from app.planning.base import Plan


@dataclass
class ConstraintViolation:
    rule: str
    message: str
    step_id: Optional[str] = None
    severity: str = "error"


@dataclass
class ConstraintResult:
    passed: bool = True
    violations: List[ConstraintViolation] = field(default_factory=list)
    score: float = 1.0

    def add(self, rule: str, message: str, step_id: Optional[str] = None,
            severity: str = "error") -> None:
        self.violations.append(ConstraintViolation(
            rule=rule, message=message, step_id=step_id, severity=severity,
        ))
        if severity == "error":
            self.passed = False
        self._recalculate_score()

    def _recalculate_score(self) -> None:
        errors = sum(1 for v in self.violations if v.severity == "error")
        warnings = sum(1 for v in self.violations if v.severity == "warning")
        total = len(self.violations) if self.violations else 1
        self.score = max(0.0, 1.0 - (errors * 0.4 + warnings * 0.1) / len(self.violations)) if self.violations else 1.0


class ConstraintEngine:
    def validate(self, plan: Plan,
                 permissions: Optional[List[str]] = None,
                 available_agents: Optional[List[str]] = None,
                 available_capabilities: Optional[List[str]] = None,
                 deadline: Optional[float] = None,
                 resource_limits: Optional[Dict[str, float]] = None,
                 policies: Optional[Dict[str, Any]] = None,
                 goal_constraints: Optional[Dict[str, Any]] = None) -> ConstraintResult:
        result = ConstraintResult()

        self._check_cycles(plan, result)
        self._check_missing_dependencies(plan, result)
        self._check_deadlines(plan, result, deadline)
        self._check_capabilities(plan, result, available_capabilities)
        self._check_agents(plan, result, available_agents)
        self._check_resource_limits(plan, result, resource_limits)
        self._check_policies(plan, result, policies)
        self._check_goal_constraints(plan, result, goal_constraints)

        return result

    def _check_cycles(self, plan: Plan, result: ConstraintResult) -> None:
        from app.planning.graph import ActionGraph
        graph = ActionGraph()
        for step in plan.steps:
            graph.add_step(step)
        for step in plan.steps:
            for dep in step.dependencies:
                graph.add_dependency(step.step_id, dep)
        if graph.has_cycles():
            cycles = graph.detect_cycles()
            for cycle in cycles:
                result.add("no_cycles", f"Cycle detected: {' -> '.join(cycle)}")

    def _check_missing_dependencies(self, plan: Plan,
                                     result: ConstraintResult) -> None:
        existing = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in existing:
                    result.add("dependencies_exist",
                               f"Step '{step.step_id}' depends on missing '{dep}'",
                               step_id=step.step_id)

    def _check_deadlines(self, plan: Plan, result: ConstraintResult,
                          deadline: Optional[float]) -> None:
        if deadline is None:
            return
        total_duration = sum(s.estimated_duration for s in plan.steps)
        if total_duration > deadline:
            result.add("deadline",
                       f"Plan duration {total_duration:.1f} exceeds deadline {deadline:.1f}",
                       severity="warning")

    def _check_capabilities(self, plan: Plan, result: ConstraintResult,
                             capabilities: Optional[List[str]]) -> None:
        if capabilities is None:
            return
        cap_set: Set[str] = set(capabilities)
        for step in plan.steps:
            if step.agent_id and step.agent_id not in cap_set:
                pass

    def _check_agents(self, plan: Plan, result: ConstraintResult,
                       agents: Optional[List[str]]) -> None:
        if agents is None:
            return
        agent_set: Set[str] = set(agents)
        for step in plan.steps:
            if step.agent_id and step.agent_id not in agent_set:
                result.add("agent_available",
                           f"Agent '{step.agent_id}' not available for step '{step.step_id}'",
                           step_id=step.step_id)

    def _check_resource_limits(self, plan: Plan, result: ConstraintResult,
                                limits: Optional[Dict[str, float]]) -> None:
        if limits is None:
            return
        total_cost = sum(s.estimated_cost for s in plan.steps)
        if "max_cost" in limits and total_cost > limits["max_cost"]:
            result.add("resource_limit",
                       f"Total cost {total_cost:.1f} exceeds limit {limits['max_cost']:.1f}",
                       severity="warning")

    def _check_policies(self, plan: Plan, result: ConstraintResult,
                         policies: Optional[Dict[str, Any]]) -> None:
        if policies is None:
            return
        if policies.get("require_agent_assignment") and any(
            s.agent_id is None for s in plan.steps
        ):
            result.add("policy_agent",
                       "Policy requires all steps have agent assignments",
                       severity="error")

    def _check_goal_constraints(self, plan: Plan, result: ConstraintResult,
                                 constraints: Optional[Dict[str, Any]]) -> None:
        if constraints is None:
            return
        if "max_cost" in constraints:
            total = sum(s.estimated_cost for s in plan.steps)
            if total > constraints["max_cost"]:
                result.add("goal_max_cost",
                           f"Plan cost {total:.1f} exceeds goal max_cost {constraints['max_cost']:.1f}",
                           severity="warning")
