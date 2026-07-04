import time
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from loguru import logger

from app.planning.base import Plan, PlanStep
from app.planning.goal import Goal
from app.planning.planner import PlanningEngine
from app.planning.action import Action
from app.mission_engine.base import Mission, MissionState, MissionPriority
from app.mission_engine.mission import MissionStore


@dataclass
class GoalPlan:
    goal_id: str
    objective: str
    description: str = ""
    sub_goals: List[Dict[str, Any]] = field(default_factory=list)
    missions: List[Dict[str, Any]] = field(default_factory=list)
    total_estimated_duration: float = 0.0
    status: str = "draft"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GoalPlanner:
    """Converts high-level objectives into executable missions.

    Pipeline: Objective → Analyze → Decompose → Plan → Tool Selection
    → Execution → Verification → Reflection → Learning.

    Reuses PlanningEngine for plan generation and MissionStore for
    mission creation.
    """

    def __init__(
        self,
        planning_engine: Optional[PlanningEngine] = None,
        mission_store: Optional[MissionStore] = None,
    ) -> None:
        self._planning = planning_engine or PlanningEngine()
        self._store = mission_store or MissionStore()
        self._goal_plans: Dict[str, GoalPlan] = {}
        self._plans_created = 0
        self._execution_count = 0

    def analyze_objective(self, objective: str) -> Dict[str, Any]:
        intent_keywords = {
            "organize": ("organization", ["file_management", "search", "categorization"]),
            "find": ("search", ["knowledge_retrieval", "file_search"]),
            "create": ("creation", ["code_generation", "file_management"]),
            "build": ("development", ["code_generation", "tool_execution"]),
            "test": ("testing", ["code_execution", "validation"]),
            "deploy": ("deployment", ["tool_execution", "system_control"]),
            "analyze": ("analysis", ["information_synthesis", "knowledge_retrieval"]),
            "research": ("research", ["web_search", "knowledge_retrieval"]),
            "clean": ("maintenance", ["file_management", "system_control"]),
            "monitor": ("monitoring", ["system_control", "data_analysis"]),
            "backup": ("backup", ["file_management", "system_control"]),
            "install": ("installation", ["tool_execution", "system_control"]),
            "update": ("update", ["tool_execution", "file_management"]),
            "configure": ("configuration", ["file_management", "tool_execution"]),
        }
        obj_lower = objective.lower()
        for keyword, (category, caps) in intent_keywords.items():
            if keyword in obj_lower:
                return {"category": category, "capabilities": caps}

        return {"category": "general", "capabilities": ["tool_execution"]}

    def decompose_objective(self, objective: str) -> List[Dict[str, Any]]:
        analysis = self.analyze_objective(objective)
        cap = analysis["capabilities"]
        steps = []

        if len(cap) >= 3:
            for c in cap:
                steps.append({
                    "name": f"{c.replace('_', ' ').title()}",
                    "capability": c,
                    "description": f"Execute {c.replace('_', ' ')} for: {objective[:80]}",
                })
        else:
            steps = [
                {"name": "Analyze", "capability": "information_synthesis",
                 "description": f"Analyze objective: {objective[:80]}"},
                {"name": "Plan", "capability": "task_decomposition",
                 "description": "Create execution plan"},
                {"name": "Execute", "capability": "tool_execution",
                 "description": f"Execute steps for: {objective[:80]}"},
                {"name": "Verify", "capability": "validation",
                 "description": "Verify results"},
            ]
        return steps

    def create_goal(
        self,
        objective: str,
        description: str = "",
        priority: float = 5.0,
    ) -> GoalPlan:
        goal_id = str(uuid.uuid4())
        sub_goals = self.decompose_objective(objective)
        goal_plan = GoalPlan(
            goal_id=goal_id,
            objective=objective,
            description=description or objective,
            sub_goals=sub_goals,
            status="planned",
        )
        self._goal_plans[goal_id] = goal_plan
        self._plans_created += 1

        goal = self._planning.create_goal(
            name=objective[:100],
            description=description or objective,
            priority=priority,
            required_capabilities=[sg["capability"] for sg in sub_goals],
        )
        goal_plan.metadata["goal_id"] = goal.goal_id

        logger.info(f"GoalPlanner: Created goal '{goal_id}' for '{objective[:60]}...'")
        return goal_plan

    async def plan_goal(self, goal_plan: GoalPlan) -> Optional[GoalPlan]:
        goal_id = goal_plan.metadata.get("goal_id", "")
        goal = self._planning.get_goal(goal_id) if goal_id else None
        if not goal:
            goal = self._planning.create_goal(
                name=goal_plan.objective[:100],
                description=goal_plan.description,
                required_capabilities=[sg["capability"] for sg in goal_plan.sub_goals],
            )
            goal_plan.metadata["goal_id"] = goal.goal_id

        plan = await self._planning.generate_plan(goal)
        if not plan:
            logger.warning(f"GoalPlanner: No plan generated for goal '{goal_plan.goal_id}'")
            goal_plan.status = "failed"
            return None

        for sub in goal_plan.sub_goals:
            mission = self._store.create(
                name=sub["name"],
                description=sub["description"],
                priority=MissionPriority.MEDIUM,
                metadata={"goal_plan_id": goal_plan.goal_id, "capability": sub["capability"]},
            )
            sub["mission_id"] = mission.id
            goal_plan.missions.append({
                "mission_id": mission.id,
                "name": mission.name,
                "status": mission.state.value,
            })

        goal_plan.total_estimated_duration = sum(
            m.get("estimated_duration", 60) for m in goal_plan.missions
        )
        goal_plan.status = "planned"
        goal_plan.metadata["plan_id"] = plan.plan_id
        goal_plan.metadata["total_duration"] = plan.total_duration
        self._goal_plans[goal_plan.goal_id] = goal_plan
        logger.info(
            f"GoalPlanner: Planned goal '{goal_plan.goal_id}' "
            f"with {len(goal_plan.missions)} missions"
        )
        return goal_plan

    def get_goal(self, goal_id: str) -> Optional[GoalPlan]:
        return self._goal_plans.get(goal_id)

    def list_goals(self, status: Optional[str] = None) -> List[GoalPlan]:
        if status:
            return [g for g in self._goal_plans.values() if g.status == status]
        return list(self._goal_plans.values())

    def update_goal_status(self, goal_id: str, status: str) -> bool:
        goal = self._goal_plans.get(goal_id)
        if not goal:
            return False
        goal.status = status
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_goals": len(self._goal_plans),
            "plans_created": self._plans_created,
            "execution_count": self._execution_count,
            "active_goals": sum(1 for g in self._goal_plans.values() if g.status == "planned"),
            "completed_goals": sum(1 for g in self._goal_plans.values() if g.status == "completed"),
            "failed_goals": sum(1 for g in self._goal_plans.values() if g.status == "failed"),
            "rejected_goals": sum(1 for g in self._goal_plans.values() if g.status == "rejected"),
        }

    async def delegate_goal(
        self,
        goal_plan: GoalPlan,
        orchestrator: Any,
        parallel: bool = True,
    ) -> Optional[GoalPlan]:
        from app.agent_orchestration.orchestrator import AgentOrchestrator
        result = await orchestrator.plan_and_delegate(
            objective=goal_plan.objective,
            description=goal_plan.description,
            parallel=parallel,
        )
        if result.get("status") == "failed":
            goal_plan.status = "failed"
            return None
        goal_plan.status = result.get("status", "completed")
        goal_plan.metadata["orchestration_result"] = result
        self._goal_plans[goal_plan.goal_id] = goal_plan
        self._execution_count += 1
        return goal_plan
