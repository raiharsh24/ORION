from dataclasses import dataclass, field
from typing import List, Dict, Set

from app.planning.base import Plan
from app.planning.graph import ActionGraph


@dataclass
class ValidationError:
    rule: str
    message: str
    step_id: str = ""
    severity: str = "error"


@dataclass
class ValidationResult:
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def add_error(self, rule: str, message: str,
                  step_id: str = "") -> None:
        self.errors.append(ValidationError(
            rule=rule, message=message, step_id=step_id, severity="error",
        ))
        self.valid = False

    def add_warning(self, rule: str, message: str,
                    step_id: str = "") -> None:
        self.warnings.append(ValidationError(
            rule=rule, message=message, step_id=step_id, severity="warning",
        ))


class PlanValidator:
    def validate(self, plan: Plan) -> ValidationResult:
        result = ValidationResult()
        if not plan.steps:
            result.add_error("no_steps", "Plan has no steps")
            return result

        self._check_cycles(plan, result)
        self._check_missing_dependencies(plan, result)
        self._check_resource_conflicts(plan, result)
        self._check_policy_violations(plan, result)
        self._check_deadlocks(plan, result)

        return result

    def _build_graph(self, plan: Plan) -> ActionGraph:
        graph = ActionGraph()
        for step in plan.steps:
            graph.add_step(step)
        for step in plan.steps:
            for dep in step.dependencies:
                graph.add_dependency(step.step_id, dep)
        return graph

    def _check_cycles(self, plan: Plan, result: ValidationResult) -> None:
        graph = self._build_graph(plan)
        cycles = graph.detect_cycles()
        for cycle in cycles:
            cycle_str = " -> ".join(cycle[:5])
            result.add_error("cycle_detected",
                             f"Circular dependency: {cycle_str}")

    def _check_missing_dependencies(self, plan: Plan,
                                     result: ValidationResult) -> None:
        existing: Set[str] = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in existing:
                    result.add_error("missing_dependency",
                                     f"Step '{step.step_id}' depends on "
                                     f"missing step '{dep}'",
                                     step_id=step.step_id)

    def _check_resource_conflicts(self, plan: Plan,
                                   result: ValidationResult) -> None:
        agent_steps: Dict[str, List[str]] = {}
        for step in plan.steps:
            if step.agent_id:
                if step.agent_id not in agent_steps:
                    agent_steps[step.agent_id] = []
                agent_steps[step.agent_id].append(step.step_id)

        graph = self._build_graph(plan)

        for agent_id, step_ids in agent_steps.items():
            if len(step_ids) <= 1:
                continue
            parallel = []
            for batch in graph.get_parallel_batches():
                batch_ids = {s.step_id for s in batch}
                concurrent = batch_ids.intersection(step_ids)
                if len(concurrent) > 1:
                    parallel.extend(concurrent)
            if len(parallel) > 1:
                result.add_warning("resource_conflict",
                                   f"Agent '{agent_id}' assigned to "
                                   f"concurrent steps: {', '.join(parallel)}")

    def _check_policy_violations(self, plan: Plan,
                                  result: ValidationResult) -> None:
        for step in plan.steps:
            if step.condition and not step.fallback_step_id:
                result.add_warning("conditional_no_fallback",
                                   f"Conditional step '{step.step_id}' "
                                   f"has no fallback",
                                   step_id=step.step_id)

    def _check_deadlocks(self, plan: Plan, result: ValidationResult) -> None:
        graph = self._build_graph(plan)
        for step in plan.steps:
            deps = graph.get_dependencies(step.step_id)
            for dep_id in deps:
                dep_step = graph.get_step(dep_id)
                if dep_step and dep_step.fallback_step_id == step.step_id:
                    result.add_error("deadlock",
                                     f"Circular fallback between "
                                     f"'{step.step_id}' and '{dep_id}'",
                                     step_id=step.step_id)
