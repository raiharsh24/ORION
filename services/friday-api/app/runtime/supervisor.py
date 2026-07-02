import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

from app.runtime.base import RecoveryAction


@dataclass
class SupervisionReport:
    issues_detected: int = 0
    recoveries_attempted: int = 0
    recoveries_succeeded: int = 0
    actions_taken: List[RecoveryAction] = field(default_factory=list)


class Supervisor:
    def __init__(self, agent_manager: Any = None,
                 executor: Any = None):
        self._agent_manager = agent_manager
        self._executor = executor
        self._timeout_handlers: Dict[str, float] = {}
        self._failure_counts: Dict[str, int] = {}
        self._max_retries = 3
        self._recovery_hooks: List[Callable] = []
        self._recovery_count = 0
        self._recovery_success = 0

    def on_recovery(self, hook: Callable) -> None:
        self._recovery_hooks.append(hook)

    def watch_timeout(self, mission_id: str, timeout_s: float) -> None:
        self._timeout_handlers[mission_id] = time.time() + timeout_s

    def unwatch_timeout(self, mission_id: str) -> None:
        self._timeout_handlers.pop(mission_id, None)

    def check_timeouts(self) -> List[str]:
        now = time.time()
        timed_out: List[str] = []
        for mid, deadline in list(self._timeout_handlers.items()):
            if now > deadline:
                timed_out.append(mid)
                self._timeout_handlers.pop(mid, None)
        return timed_out

    def record_failure(self, mission_id: str) -> int:
        self._failure_counts[mission_id] = self._failure_counts.get(mission_id, 0) + 1
        return self._failure_counts[mission_id]

    def can_retry(self, mission_id: str) -> bool:
        return self._failure_counts.get(mission_id, 0) < self._max_retries

    async def recover_timeout(self, mission_id: str) -> RecoveryAction:
        action = RecoveryAction(
            action_type="retry", target=mission_id,
            reason="Timeout detected",
        )
        self._recovery_count += 1
        if self._executor and hasattr(self._executor, 'retry_mission'):
            try:
                await self._executor.retry_mission(mission_id)
                action.status = "completed"
                action.result = "Retry succeeded"
                self._recovery_success += 1
            except Exception as e:
                action.status = "failed"
                action.result = f"Retry failed: {e}"

        for hook in self._recovery_hooks:
            try:
                hook(mission_id, action)
            except Exception:
                pass
        return action

    async def recover_failure(self, mission_id: str,
                               error: str) -> RecoveryAction:
        action = RecoveryAction(
            action_type="retry", target=mission_id,
            reason=error,
        )
        self._recovery_count += 1
        if self.can_retry(mission_id):
            if self._executor and hasattr(self._executor, 'retry_mission'):
                try:
                    await self._executor.retry_mission(mission_id)
                    action.status = "completed"
                    action.result = "Retry succeeded after failure"
                    self._recovery_success += 1
                except Exception as e:
                    action.status = "failed"
                    action.result = f"Retry failed: {e}"
        else:
            action.status = "failed"
            action.result = "Max retries exceeded"

        for hook in self._recovery_hooks:
            try:
                hook(mission_id, action)
            except Exception:
                pass
        return action

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    @property
    def recovery_success_rate(self) -> float:
        if self._recovery_count == 0:
            return 1.0
        return self._recovery_success / self._recovery_count

    @property
    def available(self) -> bool:
        return True
