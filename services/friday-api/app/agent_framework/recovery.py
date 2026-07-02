from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from app.agent_framework.persistence import PersistenceManager, CheckpointData
from app.agent_framework.delegation import DelegationManager
from app.agent_framework.blackboard import Blackboard


@dataclass
class RecoveryHealth:
    status: str = "healthy"
    last_recovery: Optional[str] = None
    total_recoveries: int = 0


@dataclass
class RecoveryReport:
    success: bool
    message: str = ""
    restored_agents: int = 0
    restored_tasks: int = 0
    restored_context_keys: int = 0
    errors: List[str] = field(default_factory=list)


class RecoveryManager:
    def __init__(self, persistence: PersistenceManager,
                 agent_manager: Optional[Any] = None,
                 delegation: Optional[DelegationManager] = None,
                 blackboard: Optional[Blackboard] = None,
                 metrics: Optional[Any] = None):
        self._persistence = persistence
        self._agent_manager = agent_manager
        self._delegation = delegation
        self._blackboard = blackboard
        self._metrics = metrics
        self._last_recovery: Optional[str] = None
        self._total_recoveries = 0

    async def recover_all(self) -> RecoveryReport:
        checkpoint = await self._persistence.warm_restart()
        if not checkpoint:
            return RecoveryReport(
                success=False, message="No checkpoint found"
            )

        report = RecoveryReport(success=True, message="Recovery completed")
        errors: List[str] = []

        try:
            restored_agents = await self._recover_agents(checkpoint)
            report.restored_agents = restored_agents
        except Exception as e:
            errors.append(f"Agent recovery failed: {e}")

        try:
            restored_tasks = await self._recover_delegated_work(checkpoint)
            report.restored_tasks = restored_tasks
        except Exception as e:
            errors.append(f"Task recovery failed: {e}")

        try:
            restored_context = await self._recover_context(checkpoint)
            report.restored_context_keys = restored_context
        except Exception as e:
            errors.append(f"Context recovery failed: {e}")

        report.errors = errors

        self._last_recovery = str(checkpoint.timestamp)
        self._total_recoveries += 1

        if self._metrics:
            self._metrics.record_recovery()

        ok_count = restored_agents + restored_tasks + restored_context
        report.message = (
            f"Restored {restored_agents} agents, {restored_tasks} tasks, "
            f"{restored_context} context keys"
        )
        report.success = ok_count > 0 or not errors
        return report

    async def recover_agent(self, agent_id: str) -> bool:
        state = await self._persistence.load_agent_state(agent_id)
        if not state or not self._agent_manager:
            return False
        agent = self._agent_manager.get_agent(agent_id)
        if agent and state.get("state"):
            from app.agent_framework.state import AgentState
            try:
                restored_state = AgentState(state["state"])
                agent.state = restored_state
            except (ValueError, KeyError):
                pass
        return True

    async def _recover_agents(self, checkpoint: CheckpointData) -> int:
        if not self._agent_manager:
            return 0
        count = 0
        for agent_id, state in checkpoint.agents.items():
            if await self.recover_agent(agent_id):
                count += 1
        return count

    async def _recover_delegated_work(self,
                                      checkpoint: CheckpointData) -> int:
        if not self._delegation:
            return 0
        count = 0
        for task_data in checkpoint.pending_tasks:
            self._delegation.restore_task(task_data)
            count += 1
        return count

    async def _recover_context(self, checkpoint: CheckpointData) -> int:
        if not self._blackboard:
            return 0
        count = 0
        for key, value in checkpoint.context_data.items():
            await self._blackboard.post(key, value, writer="system")
            count += 1
        return count

    async def cleanup_inconsistent_state(self) -> List[str]:
        errors: List[str] = []
        if self._delegation:
            try:
                for task in self._delegation.get_all_active():
                    if task.status == "running":
                        task.status = "failed"
                        task.error = "Recovery cleanup"
                        errors.append(f"Reset stuck task: {task.task_id}")
            except Exception as e:
                errors.append(f"Cleanup error: {e}")
        return errors

    def health(self) -> RecoveryHealth:
        return RecoveryHealth(
            status="healthy",
            last_recovery=self._last_recovery,
            total_recoveries=self._total_recoveries,
        )
