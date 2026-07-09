import time
import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from app.friday.planner_manager import PlannerManager
from app.friday.planner_schema import ExecutionPlan
from app.friday.intent import IntentType
from app.planner.recovery import RecoveryPolicies
from app.runtime.supervisor import Supervisor
from app.runtime.base import RecoveryAction


class UnifiedPlanner:
    def __init__(
        self,
        planner_manager: Optional[PlannerManager] = None,
        planning_engine: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
    ) -> None:
        self._planner_manager = planner_manager or PlannerManager(
            event_bus=event_bus, tool_registry=tool_registry,
        )
        self._planning_engine = planning_engine
        self._event_bus = event_bus

        self._recovery = RecoveryPolicies(event_bus=event_bus)
        self._supervisor = Supervisor()
        self._plan_count = 0
        self._fallback_count = 0

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    async def plan(
        self,
        prompt: str,
        intent_type: Optional[IntentType] = None,
        use_cognitive: bool = False,
    ) -> Optional[ExecutionPlan]:
        self._plan_count += 1

        if use_cognitive and self._planning_engine:
            return await self._cognitive_plan(prompt, intent_type)

        return await self._fast_plan(prompt, intent_type)

    async def _fast_plan(
        self,
        prompt: str,
        intent_type: Optional[IntentType] = None,
    ) -> Optional[ExecutionPlan]:
        try:
            return await self._planner_manager.create_plan(prompt, intent_type)
        except Exception as e:
            logger.warning(f"UnifiedPlanner fast plan failed: {e}")
            self._fallback_count += 1
            return self._emergency_plan(prompt)

    async def _cognitive_plan(
        self,
        prompt: str,
        intent_type: Optional[IntentType] = None,
    ) -> Optional[ExecutionPlan]:
        goal = self._planning_engine.create_goal(
            name=prompt[:80],
            description=prompt,
            priority=7.0 if intent_type and intent_type in (
                IntentType.SYSTEM_COMMAND, IntentType.FILE_OPERATION,
            ) else 5.0,
        )
        generated = await self._planning_engine.generate_plan(goal)

        if not generated or not generated.steps:
            logger.info("Cognitive plan empty, falling back to fast planner")
            self._fallback_count += 1
            return await self._fast_plan(prompt, intent_type)

        validation = await self._planning_engine.validate_plan(generated)
        if not validation.valid:
            logger.warning("Cognitive plan validation failed, falling back")
            self._fallback_count += 1
            return await self._fast_plan(prompt, intent_type)

        return self._cognitive_to_execution_plan(generated, prompt)

    def _cognitive_to_execution_plan(
        self,
        plan: Any,
        prompt: str,
    ) -> ExecutionPlan:
        steps = []
        tool_name = None
        for s in plan.steps:
            step = {
                "step_id": s.step_id,
                "action": s.action_name,
                "action_id": s.action_id,
                "agent_id": s.agent_id,
            }
            steps.append(step)
            if tool_name is None:
                tool_name = s.action_id

        return ExecutionPlan(
            intent="CognitivePlan",
            goal=plan.goal_name,
            memoryRequired=True,
            toolRequired=len(steps) > 0,
            clarificationRequired=False,
            steps=steps,
            priority="high" if len(steps) > 3 else "medium",
            confidence=plan.success_probability if hasattr(plan, "success_probability") else 0.85,
            tool_name=tool_name,
            reasoning=f"Cognitive plan with {len(steps)} steps",
        )

    def _emergency_plan(self, prompt: str) -> ExecutionPlan:
        return ExecutionPlan(
            intent="Conversation",
            goal=f"Respond to: {prompt[:60]}",
            memoryRequired=False,
            toolRequired=False,
            clarificationRequired=False,
            reasoning="Emergency fallback — no tool execution",
        )

    async def recover_plan(
        self,
        plan: ExecutionPlan,
        error: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ExecutionPlan]:
        ctx = {
            "mission_id": str(uuid.uuid4()),
            "tool_name": plan.tool_name,
            "error": error,
            **(context or {}),
        }

        if not self._supervisor.can_retry(ctx["mission_id"]):
            logger.warning(f"UnifiedPlanner max retries exceeded for {plan.tool_name}")
            return None

        self._supervisor.record_failure(ctx["mission_id"])
        strategy = self._recovery._strategies[0]
        try:
            result = strategy.execute(ctx)
            if result:
                logger.info(f"UnifiedPlanner recovery succeeded via {strategy.name}")
                return plan
        except Exception as e:
            logger.error(f"UnifiedPlanner recovery failed: {e}")

        return None

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "plans_created": self._plan_count,
            "fallbacks": self._fallback_count,
            "recovery_count": self._recovery._total_attempts,
            "recovery_successes": self._recovery._total_successes,
        }
