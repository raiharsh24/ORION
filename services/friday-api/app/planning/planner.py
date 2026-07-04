import time
import uuid
from typing import Optional, List, Dict, Any, Callable

from app.planning.base import Plan, PlanStep
from app.planning.goal import Goal
from app.planning.action import Action
from app.planning.graph import ActionGraph
from app.planning.constraints import ConstraintEngine, ConstraintResult
from app.planning.heuristics import HeuristicScorer, HeuristicScores
from app.planning.simulation import SimulationEngine, SimulationResult
from app.planning.validator import PlanValidator, ValidationResult
from app.planning.memory import PlanMemory
from app.planning.health import PlanningHealth

from app.planning.events import (
    GoalCreated, GoalUpdated, PlanGenerated, PlanValidated,
    PlanRejected, PlanOptimized, PlanExecuted, PlanArchived,
)


class PlanningEngine:
    def __init__(self, agent_manager: Any = None,
                 memory_base_path: Optional[str] = None):
        self._agent_manager = agent_manager
        self._goals: Dict[str, Goal] = {}
        self._actions: Dict[str, Action] = {}
        self._constraint_engine = ConstraintEngine()
        self._heuristic_scorer = HeuristicScorer()
        self._simulator = SimulationEngine()
        self._validator = PlanValidator()
        self._memory = PlanMemory(base_path=memory_base_path)
        self._event_bus = None
        self._planning_times: List[float] = []
        self._plans_generated = 0
        self._validation_failures = 0
        self._on_generate_hooks: List[Callable] = []

        self._register_default_actions()

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    def on_generate(self, hook: Callable) -> None:
        self._on_generate_hooks.append(hook)

    def _register_default_actions(self) -> None:
        defaults = [
            Action("research", "Research", "Gather information",
                   required_capabilities=["web_search", "knowledge_retrieval"],
                   estimated_cost=2.0, estimated_duration=3.0),
            Action("analyze", "Analyze", "Process and analyze data",
                   required_capabilities=["information_synthesis"],
                   estimated_cost=3.0, estimated_duration=2.0),
            Action("code", "Code Generation", "Write or modify code",
                   required_capabilities=["code_generation"],
                   estimated_cost=5.0, estimated_duration=5.0),
            Action("test", "Testing", "Run tests and verify",
                   required_capabilities=["code_review", "code_execution"],
                   estimated_cost=2.0, estimated_duration=2.0),
            Action("deploy", "Deploy", "Deploy to target environment",
                   required_capabilities=["tool_execution"],
                   estimated_cost=3.0, estimated_duration=1.0),
            Action("browse", "Web Browsing", "Navigate and extract web content",
                   required_capabilities=["web_navigation", "content_extraction"],
                   estimated_cost=1.0, estimated_duration=2.0),
            Action("plan", "Planning", "Decompose tasks and plan execution",
                   required_capabilities=["task_decomposition"],
                   estimated_cost=1.0, estimated_duration=1.0),
        ]
        for a in defaults:
            self._actions[a.action_id] = a

    def register_action(self, action: Action) -> None:
        self._actions[action.action_id] = action

    def create_goal(self, name: str, description: str = "",
                    priority: float = 5.0,
                    deadline: Optional[float] = None,
                    required_capabilities: Optional[List[str]] = None,
                    success_criteria: Optional[List[str]] = None,
                    constraints: Optional[Dict[str, Any]] = None
                    ) -> Goal:
        goal_id = str(uuid.uuid4())
        goal = Goal(
            goal_id=goal_id,
            name=name,
            description=description,
            priority=priority,
            required_capabilities=required_capabilities or [],
            success_criteria=success_criteria or [],
            constraints=constraints or {},
        )
        self._goals[goal_id] = goal
        self._publish_event(GoalCreated(goal_id, name, priority))
        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def update_goal_status(self, goal_id: str, status: str) -> bool:
        goal = self._goals.get(goal_id)
        if not goal:
            return False
        goal.status = status
        self._publish_event(GoalUpdated(goal_id, status))
        return True

    def decompose_goal(self, goal: Goal) -> List[Goal]:
        sub_goals: List[Goal] = []
        caps = goal.required_capabilities or []
        for i, cap in enumerate(caps):
            sub = Goal(
                goal_id=str(uuid.uuid4()),
                name=f"{goal.name}:{cap}",
                description=f"Sub-goal for {cap}",
                priority=goal.priority,
                required_capabilities=[cap],
                success_criteria=goal.success_criteria,
                parent_goal_id=goal.goal_id,
            )
            self._goals[sub.goal_id] = sub
            goal.add_child(sub.goal_id)
            sub_goals.append(sub)

        if len(caps) <= 1 and not sub_goals:
            sub = Goal(
                goal_id=str(uuid.uuid4()),
                name=f"{goal.name}:default",
                description="Default sub-goal",
                priority=goal.priority,
                parent_goal_id=goal.goal_id,
            )
            self._goals[sub.goal_id] = sub
            goal.add_child(sub.goal_id)
            sub_goals.append(sub)

        return sub_goals

    async def generate_plan(self, goal: Goal) -> Optional[Plan]:
        start_time = time.time()
        plan_id = str(uuid.uuid4())

        sub_goals = self.decompose_goal(goal)

        steps: List[PlanStep] = []
        prev_step_id: Optional[str] = None

        for i, sub in enumerate(sub_goals):
            matching = self._find_matching_actions(sub)
            if not matching:
                continue

            action = matching[0]
            step_id = str(uuid.uuid4())
            step = PlanStep(
                step_id=step_id,
                action_id=action.action_id,
                action_name=action.name,
                dependencies=[prev_step_id] if prev_step_id else [],
                estimated_cost=action.estimated_cost,
                estimated_duration=action.estimated_duration,
                parallel_group="group_0" if i % 2 == 1 and prev_step_id else None,
            )
            steps.append(step)
            if not step.parallel_group:
                prev_step_id = step_id

        if not steps:
            steps.append(PlanStep(
                step_id=str(uuid.uuid4()),
                action_id="plan",
                action_name="Planning",
                estimated_cost=1.0,
                estimated_duration=1.0,
            ))

        plan = Plan(
            plan_id=plan_id,
            goal_id=goal.goal_id,
            goal_name=goal.name,
            steps=steps,
            total_cost=sum(s.estimated_cost for s in steps),
            total_duration=sum(s.estimated_duration for s in steps),
        )

        sim_result = self.simulate_plan(plan)
        plan.risk_score = sim_result.risk_score
        plan.success_probability = sim_result.success_probability

        heur_result = self._heuristic_scorer.score(plan)
        plan.metadata["heuristic_score"] = heur_result.total
        plan.metadata["heuristic_details"] = {
            "complexity": heur_result.complexity,
            "cost": heur_result.cost,
            "latency": heur_result.latency,
            "parallelism": heur_result.parallelism,
            "dependency_depth": heur_result.dependency_depth,
            "risk": heur_result.risk,
        }

        plan.status = "generated"
        self._plans_generated += 1
        elapsed = (time.time() - start_time) * 1000
        self._planning_times.append(elapsed)

        for hook in self._on_generate_hooks:
            try:
                hook(plan)
            except Exception:
                pass

        await self._memory.save_plan(plan)
        self._publish_event(PlanGenerated(plan_id, goal.goal_id, len(steps)))
        return plan

    async def validate_plan(self, plan: Plan) -> ValidationResult:
        result = self._validator.validate(plan)
        if not result.valid:
            self._validation_failures += 1
            self._publish_event(PlanRejected(
                plan.plan_id,
                "; ".join(e.message for e in result.errors[:3]),
            ))
        self._publish_event(PlanValidated(
            plan.plan_id, result.valid, result.error_count,
        ))
        return result

    def simulate_plan(self, plan: Plan) -> SimulationResult:
        return self._simulator.simulate(plan)

    async def optimize_plan(self, plan: Plan) -> Plan:
        before = plan.metadata.get("heuristic_score", 0.5)

        graph = ActionGraph()
        for step in plan.steps:
            graph.add_step(step)
        for step in plan.steps:
            for dep in step.dependencies:
                graph.add_dependency(step.step_id, dep)

        batches = graph.get_parallel_batches()
        if len(batches) > 1:
            before_parallel = self._heuristic_scorer.score(plan).parallelism

        optimized_steps: List[PlanStep] = []
        for step in plan.steps:
            opt = PlanStep(
                step_id=step.step_id,
                action_id=step.action_id,
                action_name=step.action_name,
                agent_id=step.agent_id,
                dependencies=list(step.dependencies),
                parallel_group=step.parallel_group,
                condition=step.condition,
                estimated_cost=step.estimated_cost * 0.9,
                estimated_duration=step.estimated_duration * 0.9,
                metadata=step.metadata,
            )
            optimized_steps.append(opt)

        plan.steps = optimized_steps
        plan.total_cost = sum(s.estimated_cost for s in optimized_steps)
        plan.total_duration = sum(s.estimated_duration for s in optimized_steps)
        plan.version += 1

        after = self._heuristic_scorer.score(plan).total
        plan.metadata["heuristic_score"] = after
        plan.metadata["optimization_applied"] = True
        plan.metadata["score_improvement"] = round(after - before, 3)

        self._publish_event(PlanOptimized(plan.plan_id, before, after))
        await self._memory.save_plan(plan)
        return plan

    async def revise_plan(self, plan: Plan,
                          feedback: Dict[str, Any]) -> Optional[Plan]:
        revision = Plan(
            plan_id=str(uuid.uuid4()),
            goal_id=plan.goal_id,
            goal_name=plan.goal_name,
            version=plan.version + 1,
            metadata={**plan.metadata, "revision_of": plan.plan_id,
                      "feedback": feedback},
        )

        for step in plan.steps:
            if step.step_id in feedback.get("remove_steps", []):
                continue
            if step.step_id in feedback.get("modify_steps", {}):
                mods = feedback["modify_steps"][step.step_id]
                revised = PlanStep(
                    step_id=step.step_id,
                    action_id=mods.get("action_id", step.action_id),
                    action_name=mods.get("action_name", step.action_name),
                    agent_id=mods.get("agent_id", step.agent_id),
                    dependencies=list(step.dependencies),
                    parallel_group=step.parallel_group,
                    condition=step.condition,
                    estimated_cost=mods.get("estimated_cost",
                                            step.estimated_cost),
                    estimated_duration=mods.get("estimated_duration",
                                                step.estimated_duration),
                    metadata=step.metadata,
                )
                revision.add_step(revised)
            else:
                revision.add_step(PlanStep(
                    step_id=step.step_id,
                    action_id=step.action_id,
                    action_name=step.action_name,
                    agent_id=step.agent_id,
                    dependencies=list(step.dependencies),
                    parallel_group=step.parallel_group,
                    condition=step.condition,
                    fallback_step_id=step.fallback_step_id,
                    estimated_cost=step.estimated_cost,
                    estimated_duration=step.estimated_duration,
                    metadata=step.metadata,
                ))

        add_steps = feedback.get("add_steps", [])
        for add in add_steps:
            revision.add_step(PlanStep(
                step_id=str(uuid.uuid4()),
                action_id=add.get("action_id", "plan"),
                action_name=add.get("action_name", "Additional step"),
                dependencies=add.get("dependencies", []),
                estimated_cost=add.get("estimated_cost", 1.0),
                estimated_duration=add.get("estimated_duration", 1.0),
            ))

        revision.total_cost = sum(s.estimated_cost for s in revision.steps)
        revision.total_duration = sum(s.estimated_duration
                                      for s in revision.steps)
        revision.status = "revised"
        await self._memory.save_plan(revision)
        return revision

    async def execute_plan(self, plan: Plan) -> bool:
        if not self._agent_manager:
            return False

        plan.status = "executing"
        success = True

        for step in plan.steps:
            if not step.agent_id:
                if self._agent_manager:
                    candidates = self._agent_manager.find_agents_for_task(
                        step.action_id)
                    if candidates:
                        step.agent_id = candidates[0].agent_id
                    else:
                        step.status = "failed"
                        success = False
                        continue

            result = await self._agent_manager.execute_task(
                step.agent_id, step.action_id, {"step_id": step.step_id},
            )
            step.status = "completed" if result is not None else "failed"
            if result is None:
                success = False

        plan.status = "completed" if success else "failed"
        plan.executed_at = plan.created_at

        self._publish_event(PlanExecuted(plan.plan_id, plan.goal_id, success))
        await self._memory.save_plan(plan)
        return success

    async def archive_plan(self, plan_id: str) -> bool:
        plan = await self._memory.load_plan(plan_id)
        if not plan:
            return False
        result = await self._memory.archive_plan(plan_id)
        if result:
            self._publish_event(PlanArchived(plan_id, plan.goal_name))
        return result

    async def find_similar_plans(self, goal: Goal) -> List[Plan]:
        return await self._memory.find_similar(
            goal.name, goal.required_capabilities)

    async def store_template(self, template_id: str, plan: Plan) -> None:
        await self._memory.store_template(template_id, plan)

    async def load_template(self, template_id: str) -> Optional[Plan]:
        return await self._memory.load_template(template_id)

    async def check_constraints(self, goal: Goal,
                                 plan: Plan) -> ConstraintResult:
        agents = None
        capabilities = None
        if self._agent_manager:
            agents = [a.agent_id for a in self._agent_manager.list_agents()]
            all_caps = set()
            for a in self._agent_manager.list_agents():
                for c in a.capabilities:
                    all_caps.add(c.name)
            capabilities = list(all_caps)

        return self._constraint_engine.validate(
            plan, available_agents=agents,
            available_capabilities=capabilities,
            deadline=goal.deadline.timestamp() if goal.deadline else None,
            goal_constraints=goal.constraints,
        )

    def score_plan(self, plan: Plan) -> HeuristicScores:
        return self._heuristic_scorer.score(plan)

    def memory_stats(self) -> Dict[str, Any]:
        return self._memory.get_statistics()

    async def clear_memory(self) -> None:
        await self._memory.clear()

    def _find_matching_actions(self, goal: Goal) -> List[Action]:
        if not goal.required_capabilities:
            return list(self._actions.values())
        matching = []
        for action in self._actions.values():
            if any(cap in action.required_capabilities
                   for cap in (goal.required_capabilities or [])):
                matching.append(action)
        return matching

    def _publish_event(self, event: Any) -> None:
        if self._event_bus:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    self._event_bus.publish_background(event)
            except RuntimeError:
                pass

    def health(self) -> PlanningHealth:
        avg_time = 0.0
        if self._planning_times:
            avg_time = sum(self._planning_times) / len(self._planning_times)

        stats = self._memory.get_statistics()
        cached = len(list(
            filter(lambda k: k.startswith("plan_"),
                   [p for p in self._memory._cache.keys()])
        )) if hasattr(self._memory, '_cache') else 0

        return PlanningHealth(
            status="healthy",
            plans_generated=self._plans_generated,
            average_planning_time_ms=round(avg_time, 2),
            validation_failures=self._validation_failures,
            cache_hits=stats.get("cache_hits", 0),
            total_goals=len(self._goals),
            active_goals=sum(1 for g in self._goals.values()
                             if g.status == "active"),
            plans_cached=len(self._memory._cache) if hasattr(self._memory, '_cache') else 0,
            template_count=stats.get("template_matches", 0),
        )
