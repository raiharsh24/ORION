import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone

from app.runtime.base import Mission, MissionStage, ExecutionResult, RecoveryAction
from app.runtime.state import MissionStateMachine
from app.runtime.dispatcher import Dispatcher, DispatchStrategy


@dataclass
class Checkpoint:
    mission_id: str
    stage: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class MissionExecutor:
    def __init__(self, agent_manager: Any = None,
                 workflow_engine: Any = None,
                 tool_execution_engine: Any = None,
                 plugin_runtime: Any = None,
                 dispatcher: Optional[Dispatcher] = None):
        self._agent_manager = agent_manager
        self._workflow_engine = workflow_engine
        self._tool_execution_engine = tool_execution_engine
        self._plugin_runtime = plugin_runtime
        self._dispatcher = dispatcher or Dispatcher(
            agent_manager=agent_manager,
            workflow_engine=workflow_engine,
            tool_executor=tool_execution_engine,
            plugin_runtime=plugin_runtime,
        )
        self._missions: Dict[str, Mission] = {}
        self._state_machines: Dict[str, MissionStateMachine] = {}
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._paused_missions: Dict[str, Mission] = {}
        self._on_stage_hooks: List[Callable] = []

    def on_stage(self, hook: Callable) -> None:
        self._on_stage_hooks.append(hook)

    def register_mission(self, mission: Mission) -> Mission:
        self._missions[mission.mission_id] = mission
        self._state_machines[mission.mission_id] = MissionStateMachine(mission.status)
        return mission

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self._missions.get(mission_id)

    def get_state(self, mission_id: str) -> Optional[MissionStateMachine]:
        return self._state_machines.get(mission_id)

    async def execute_mission(self, mission: Mission,
                               plan: Any = None,
                               selection_result: Any = None) -> ExecutionResult:
        sm = self._state_machines.get(mission.mission_id)
        if not sm:
            sm = MissionStateMachine("created")
            self._state_machines[mission.mission_id] = sm

        start_time = time.time()

        dispatch = self._dispatcher.dispatch(mission)
        mission.metadata["dispatch_strategy"] = dispatch.strategy.value
        mission.metadata["dispatch_reason"] = dispatch.reason

        if sm.can_transition("planning"):
            sm.transition("planning")
            mission.set_status("planning")
        if sm.can_transition("ready"):
            sm.transition("ready")
            mission.set_status("ready")
        if sm.can_transition("running"):
            sm.transition("running")
            mission.set_status("running")

        self._save_checkpoint(mission, "started")
        self._trigger_hooks(mission, "running")

        success = True
        stages_completed = 0
        agent_ids = dispatch.agent_ids

        strategy = dispatch.strategy

        if strategy == DispatchStrategy.WORKFLOW_ENGINE:
            ok = await self._execute_workflow(mission, plan)
            if ok:
                stages_completed += 1
            success = ok

        elif strategy == DispatchStrategy.TOOL_EXECUTION:
            ok = await self._execute_tool(mission, selection_result)
            if ok:
                stages_completed += 1
            success = ok

        elif strategy == DispatchStrategy.SINGLE_AGENT and agent_ids:
            ok = await self._execute_single_agent(mission, agent_ids[0])
            if ok:
                stages_completed += 1
            success = ok

        elif strategy == DispatchStrategy.PARALLEL_AGENTS and agent_ids:
            ok = await self._execute_parallel_agents(mission, agent_ids)
            if ok:
                stages_completed += 1
            success = ok

        elif strategy == DispatchStrategy.PLUGIN_EXECUTION:
            ok = await self._execute_plugin(mission)
            if ok:
                stages_completed += 1
            success = ok

        else:
            stages_completed += 1
            success = True

        total_ms = (time.time() - start_time) * 1000

        if success:
            if sm.can_transition("completed"):
                sm.transition("completed")
            mission.set_status("completed")
        else:
            if sm.can_transition("failed"):
                sm.transition("failed")
            mission.set_status("failed")
            mission.error = f"Execution failed via {strategy.value}"

        self._save_checkpoint(mission, mission.status)
        self._trigger_hooks(mission, mission.status)

        return ExecutionResult(
            success=success,
            mission_id=mission.mission_id,
            stages_completed=stages_completed,
            total_duration_ms=total_ms,
            error=mission.error,
        )

    async def retry_mission(self, mission_id: str) -> bool:
        mission = self._missions.get(mission_id)
        if not mission:
            return False
        sm = self._state_machines.get(mission_id)
        if sm and sm.can_transition("running"):
            sm.transition("running")
            mission.set_status("running")
            mission.error = None
            result = await self.execute_mission(mission)
            return result.success
        return False

    async def pause_mission(self, mission_id: str) -> bool:
        mission = self._missions.get(mission_id)
        sm = self._state_machines.get(mission_id)
        if mission and sm and sm.can_transition("paused"):
            sm.transition("paused")
            mission.set_status("paused")
            self._paused_missions[mission_id] = mission
            self._save_checkpoint(mission, "paused")
            return True
        return False

    async def resume_mission(self, mission_id: str) -> bool:
        mission = self._paused_missions.pop(mission_id, None)
        if not mission:
            return False
        sm = self._state_machines.get(mission_id)
        if sm and sm.can_transition("running"):
            sm.transition("running")
            mission.set_status("running")
            self._save_checkpoint(mission, "resumed")
            return True
        return False

    async def cancel_mission(self, mission_id: str) -> bool:
        mission = self._missions.get(mission_id)
        sm = self._state_machines.get(mission_id)
        if mission and sm:
            if sm.can_transition("failed"):
                sm.transition("failed")
                mission.set_status("failed")
                mission.error = "Mission cancelled"
                self._save_checkpoint(mission, "cancelled")
                return True
        return False

    async def rollback_mission(self, mission_id: str) -> bool:
        checkpoint = self._checkpoints.get(mission_id)
        if not checkpoint:
            return False
        mission = self._missions.get(mission_id)
        if mission:
            mission.set_status("ready")
            sm = self._state_machines.get(mission_id)
            if sm:
                sm.reset("ready")
            return True
        return False

    async def _execute_single_agent(self, mission: Mission,
                                     agent_id: str) -> bool:
        if not self._agent_manager or not hasattr(self._agent_manager, "execute_task"):
            return False
        try:
            result = await self._agent_manager.execute_task(
                agent_id, "mission", {"user_request": mission.user_request},
            )
            return result is not None
        except Exception:
            return False

    async def _execute_parallel_agents(self, mission: Mission,
                                        agent_ids: List[str]) -> bool:
        if not self._agent_manager or not hasattr(self._agent_manager, "execute_task"):
            return False
        import asyncio
        results = await asyncio.gather(*[
            self._agent_manager.execute_task(
                aid, "mission", {"user_request": mission.user_request},
            )
            for aid in agent_ids
        ], return_exceptions=True)
        return any(r is not None and not isinstance(r, Exception) for r in results)

    async def _execute_workflow(self, mission: Mission,
                                 plan: Any = None) -> bool:
        if not self._workflow_engine:
            return False
        try:
            if hasattr(self._workflow_engine, "execute"):
                from app.workflow_engine.base import (
                    WorkflowGraph, WorkflowNode, WorkflowNodeType,
                )
                graph = WorkflowGraph(
                    entry_node_ids=[],
                    metadata={"mission_id": mission.mission_id,
                              "user_request": mission.user_request},
                )
                node_id = "mission_exec"
                graph.add_node(WorkflowNode(
                    id=node_id,
                    name=f"mission:{mission.mission_id}",
                    node_type=WorkflowNodeType.TOOL,
                    tool_id="mission_runtime",
                    args={"user_request": mission.user_request},
                ))
                graph.entry_node_ids.append(node_id)

                result = await self._workflow_engine.execute(graph)
                return (getattr(result, "status", None) == "completed"
                        if hasattr(result, "status") else result is not None)
        except Exception:
            return False
        return False

    async def _execute_tool(self, mission: Mission,
                             selection_result: Any = None) -> bool:
        if not self._tool_execution_engine:
            return False
        try:
            if hasattr(self._tool_execution_engine, "execute"):
                if selection_result is not None:
                    result = await self._tool_execution_engine.execute(
                        selection_result,
                    )
                else:
                    from app.tool_selection.base import (
                        ToolSelectionResult, SelectedTool,
                    )
                    fallback = ToolSelectionResult()
                    result = await self._tool_execution_engine.execute(fallback)
                return (getattr(result, "all_succeeded", False)
                        or getattr(result, "status", None) == "completed"
                        or result is not None)
        except Exception:
            return False
        return False

    async def _execute_plugin(self, mission: Mission) -> bool:
        if not self._plugin_runtime or not hasattr(self._plugin_runtime, "execute"):
            return False
        try:
            result = await self._plugin_runtime.execute(
                "mission_handler",
                mission,  # type: ignore
            )
            return result is not None
        except Exception:
            return False

    def _save_checkpoint(self, mission: Mission, stage: str) -> None:
        self._checkpoints[mission.mission_id] = Checkpoint(
            mission_id=mission.mission_id,
            stage=stage,
            data={
                "status": mission.status,
                "stages": len(mission.stages),
                "metadata": dict(mission.metadata),
            },
            timestamp=time.time(),
        )

    def _trigger_hooks(self, mission: Mission, stage: str) -> None:
        for hook in self._on_stage_hooks:
            try:
                hook(mission, stage)
            except Exception:
                pass

    def remove_mission(self, mission_id: str) -> None:
        """Clean up executor state for a completed/failed/archived mission."""
        self._missions.pop(mission_id, None)
        self._state_machines.pop(mission_id, None)
        self._checkpoints.pop(mission_id, None)
        self._paused_missions.pop(mission_id, None)

    @property
    def available(self) -> bool:
        return True

    @property
    def active_mission_count(self) -> int:
        return len(self._missions) - len(self._paused_missions)

    @property
    def paused_mission_count(self) -> int:
        return len(self._paused_missions)
