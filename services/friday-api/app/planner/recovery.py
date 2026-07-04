import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from loguru import logger

from app.mission_engine.base import MissionState
from app.events.events import FridayEvent


@dataclass
class RecoveryStrategy:
    name: str
    priority: int
    condition: Callable[[Dict[str, Any]], bool]
    execute: Callable[[Dict[str, Any]], Any]


@dataclass
class RecoveryAttempt:
    mission_id: str
    strategy: str
    reason: str
    success: bool = False
    duration_ms: float = 0.0
    result: str = ""
    timestamp: float = field(default_factory=time.time)


class RecoveryPolicies:
    """Reusable recovery strategy registry for the Mission Runtime.

    Strategies: Retry → Alternative Tool → Alternative Workflow
    → Ask User → Abort → Learn.

    Mission Runtime automatically chooses the correct strategy based on
    failure context and strategy priority.
    """

    def __init__(self, executor: Any = None, event_bus: Any = None) -> None:
        self._executor = executor
        self._event_bus = event_bus
        self._strategies: List[RecoveryStrategy] = []
        self._attempts: List[RecoveryAttempt] = []
        self._failure_counts: Dict[str, int] = {}
        self._max_retries = 3
        self._total_attempts = 0
        self._total_successes = 0

        self._register_defaults()

    def _publish(self, topic: str, data: Dict[str, Any]) -> None:
        if not self._event_bus:
            return
        try:
            self._event_bus.publish_background(FridayEvent(topic=topic, data=data))
        except Exception:
            pass

    def _register_defaults(self) -> None:
        self.register_strategy(RecoveryStrategy(
            name="retry",
            priority=10,
            condition=lambda ctx: self._failure_counts.get(
                ctx.get("mission_id", ""), 0
            ) < self._max_retries,
            execute=self._execute_retry,
        ))
        self.register_strategy(RecoveryStrategy(
            name="alternative_tool",
            priority=20,
            condition=lambda ctx: ctx.get("tool_name") is not None,
            execute=self._execute_alternative_tool,
        ))
        self.register_strategy(RecoveryStrategy(
            name="alternative_workflow",
            priority=30,
            condition=lambda ctx: ctx.get("workflow_id") is not None,
            execute=self._execute_alternative_workflow,
        ))
        self.register_strategy(RecoveryStrategy(
            name="ask_user",
            priority=40,
            condition=lambda ctx: True,
            execute=self._execute_ask_user,
        ))
        self.register_strategy(RecoveryStrategy(
            name="abort",
            priority=50,
            condition=lambda ctx: True,
            execute=self._execute_abort,
        ))

    def register_strategy(self, strategy: RecoveryStrategy) -> None:
        self._strategies.append(strategy)
        self._strategies.sort(key=lambda s: s.priority)

    async def recover(self, mission_id: str, context: Dict[str, Any]) -> RecoveryAttempt:
        self._failure_counts[mission_id] = self._failure_counts.get(mission_id, 0) + 1
        failure_count = self._failure_counts[mission_id]
        context["failure_count"] = failure_count
        context["mission_id"] = mission_id

        logger.info(
            f"RecoveryPolicies: Attempting recovery for {mission_id} "
            f"(failure #{failure_count})"
        )

        for strategy in self._strategies:
            if not strategy.condition(context):
                logger.debug(f"Strategy '{strategy.name}' condition not met, skipping")
                continue

            start = time.time()
            try:
                result = await strategy.execute(context)
                elapsed = (time.time() - start) * 1000
                success = result is not False and result is not None

                attempt = RecoveryAttempt(
                    mission_id=mission_id,
                    strategy=strategy.name,
                    reason=context.get("error", "unknown"),
                    success=success,
                    duration_ms=round(elapsed, 2),
                    result=str(result) if result else "",
                )
                self._attempts.append(attempt)
                self._total_attempts += 1

                if success:
                    self._total_successes += 1
                    self._publish("MissionRecovered", {
                        "mission_id": mission_id,
                        "strategy": strategy.name,
                        "failure_count": failure_count,
                    })
                    logger.info(
                        f"Recovery succeeded using '{strategy.name}' "
                        f"in {elapsed:.0f}ms"
                    )
                    return attempt
                else:
                    logger.warning(
                        f"Strategy '{strategy.name}' failed, "
                        f"trying next strategy..."
                    )
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                logger.error(f"Strategy '{strategy.name}' raised exception: {e}")

        # All strategies exhausted
        fallback = RecoveryAttempt(
            mission_id=mission_id,
            strategy="abort",
            reason=context.get("error", "all strategies exhausted"),
            success=False,
            result="All recovery strategies exhausted",
        )
        self._attempts.append(fallback)
        self._total_attempts += 1
        return fallback

    async def _execute_retry(self, ctx: Dict[str, Any]) -> Any:
        mission_id = ctx.get("mission_id", "")
        if self._executor and hasattr(self._executor, "retry_failed_workflow"):
            workflow_id = ctx.get("workflow_id")
            if workflow_id:
                return await self._executor.retry_failed_workflow(mission_id, workflow_id)
        return None

    async def _execute_alternative_tool(self, ctx: Dict[str, Any]) -> Any:
        logger.info(f"Alternative tool recovery for {ctx.get('mission_id')}")
        alt_tool_map = {
            "terminal": "filesystem",
            "browser": "knowledge.search",
            "filesystem": "terminal",
        }
        tool_name = ctx.get("tool_name", "")
        alt_tool = alt_tool_map.get(tool_name)
        if alt_tool:
            ctx["alternative_tool"] = alt_tool
            return alt_tool
        return False

    async def _execute_alternative_workflow(self, ctx: Dict[str, Any]) -> Any:
        logger.info(f"Alternative workflow recovery for {ctx.get('mission_id')}")
        return False

    async def _execute_ask_user(self, ctx: Dict[str, Any]) -> Any:
        logger.info(f"Ask user recovery for {ctx.get('mission_id')}")
        self._publish("UserInputRequired", {
            "mission_id": ctx.get("mission_id", ""),
            "error": ctx.get("error", "unknown"),
            "failure_count": ctx.get("failure_count", 0),
        })
        return True

    async def _execute_abort(self, ctx: Dict[str, Any]) -> Any:
        logger.warning(f"Aborting mission {ctx.get('mission_id')}")
        mission_id = ctx.get("mission_id", "")
        if self._executor and hasattr(self._executor, "cancel_mission"):
            await self._executor.cancel_mission(
                mission_id, reason="All recovery strategies exhausted"
            )
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_attempts": self._total_attempts,
            "total_successes": self._total_successes,
            "success_rate": round(
                self._total_successes / max(self._total_attempts, 1), 3
            ),
            "strategy_counts": {
                s.name: sum(1 for a in self._attempts if a.strategy == s.name)
                for s in self._strategies
            },
            "strategy_successes": {
                s.name: sum(
                    1 for a in self._attempts
                    if a.strategy == s.name and a.success
                )
                for s in self._strategies
            },
            "recent_attempts": [
                {"mission_id": a.mission_id, "strategy": a.strategy,
                 "success": a.success, "duration_ms": a.duration_ms}
                for a in self._attempts[-20:]
            ],
        }
