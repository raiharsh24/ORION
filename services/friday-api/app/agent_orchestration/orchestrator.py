import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Set, Callable
from dataclasses import dataclass, field
from loguru import logger

from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.agent_framework.agent import create_all_builtin_agents, BUILTIN_AGENTS
from app.agent_framework.state import AgentState
from app.agent_orchestration.shared_context import SharedMissionContext
from app.agent_orchestration.human_oversight import HumanOversightManager
from app.agent_orchestration.metrics import AgentMissionMetrics
from app.agent_orchestration.events import (
    AgentMissionDelegated, AgentMissionCompleted, AgentMissionFailed,
    AgentAssistanceRequested, AgentFindingsPublished,
)


class AgentOrchestrator:
    def __init__(
        self,
        agent_manager: Any = None,
        goal_planner: Any = None,
        mission_executor: Any = None,
        event_bus: Optional[EventBus] = None,
        knowledge_graph: Any = None,
        episodic_memory: Any = None,
    ) -> None:
        from app.agent_framework.manager import AgentManager

        self._agent_manager = agent_manager or AgentManager()
        self._goal_planner = goal_planner
        self._mission_executor = mission_executor
        self._event_bus = event_bus
        self._knowledge_graph = knowledge_graph
        self._episodic_memory = episodic_memory

        self._shared_contexts: Dict[str, SharedMissionContext] = {}
        self._mission_agent_map: Dict[str, str] = {}
        self._agent_mission_map: Dict[str, List[str]] = {}
        self._human_oversight = HumanOversightManager(event_bus=event_bus)
        self._metrics = AgentMissionMetrics()
        self._pending_parallel_groups: List[List[str]] = []

        self._register_builtin_agents()
        self._subscribe_events()

    def _register_builtin_agents(self) -> None:
        agents = create_all_builtin_agents()
        for agent in agents:
            self._agent_manager.create_agent(
                agent_id=agent.agent_id,
                name=agent.name,
                role=agent.role,
                capabilities=[c.name for c in agent.capabilities],
                tools=agent.tools,
                permissions=agent.permissions,
                priority=agent.priority,
            )
        logger.info(
            f"AgentOrchestrator: Registered {len(agents)} built-in agents"
        )

    def _subscribe_events(self) -> None:
        if not self._event_bus:
            return
        self._event_bus.subscribe(
            "agent.assistance.requested", self._on_assistance_requested
        )
        self._event_bus.subscribe(
            "agent.findings.published", self._on_findings_published
        )
        self._event_bus.subscribe(
            "human.approval.granted", self._on_approval_granted
        )
        self._event_bus.subscribe(
            "human.approval.denied", self._on_approval_denied
        )

    async def _on_assistance_requested(self, event: FridayEvent) -> None:
        data = event.data
        agent_id = data.get("agent_id", "")
        capability = data.get("capability_needed", "")
        mission_id = data.get("mission_id", "")

        helpers = self._agent_manager.find_by_capability(capability)
        helpers = [h for h in helpers if h.agent_id != agent_id and h.is_idle]
        if helpers:
            helper = helpers[0]
            logger.info(
                f"AgentOrchestrator: {agent_id} -> {helper.agent_id} "
                f"for capability '{capability}'"
            )

    async def _on_findings_published(self, event: FridayEvent) -> None:
        data = event.data
        mission_id = data.get("mission_id", "")
        findings = data.get("findings", "")
        ctx = self._shared_contexts.get(mission_id)
        if ctx and findings:
            ctx.write_shared(f"findings:{data.get('topic', 'general')}", findings)

    async def _on_approval_granted(self, event: FridayEvent) -> None:
        mission_id = event.data.get("mission_id", "")
        await self._human_oversight.approve(mission_id)

    async def _on_approval_denied(self, event: FridayEvent) -> None:
        mission_id = event.data.get("mission_id", "")
        await self._human_oversight.deny(mission_id)

    async def plan_and_delegate(
        self,
        objective: str,
        description: str = "",
        require_approval: bool = False,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        from app.planner.goal_planner import GoalPlanner

        planner = self._goal_planner or GoalPlanner()
        goal_plan = planner.create_goal(
            objective=objective, description=description,
        )

        goal_plan = await planner.plan_goal(goal_plan)
        if not goal_plan:
            return {"status": "failed", "error": "Goal planning failed"}

        total_duration = goal_plan.total_estimated_duration

        if require_approval:
            agent_ids = ["planner-agent"] + [
                sg.get("capability", "") for sg in goal_plan.sub_goals
            ]
            approved = await self._human_oversight.request_approval(
                mission_id=goal_plan.goal_id,
                objective=objective,
                agent_ids=agent_ids,
                estimated_duration_ms=total_duration,
            )
            if not approved:
                goal_plan.status = "rejected"
                return {"status": "rejected", "goal_plan_id": goal_plan.goal_id}

        ctx = SharedMissionContext(
            mission_id=goal_plan.goal_id,
            knowledge_graph=self._knowledge_graph,
            episodic_memory=self._episodic_memory,
        )
        self._shared_contexts[goal_plan.goal_id] = ctx

        delegated_missions = []
        for sub in goal_plan.sub_goals:
            capability = sub.get("capability", "tool_execution")
            mission_name = sub.get("name", "Unnamed")
            agent = self._select_agent_for_capability(capability)
            mission = self._create_agent_mission(
                goal_plan.goal_id, mission_name, capability, agent, sub,
            )
            delegated_missions.append(mission)

        goal_plan.metadata["agent_count"] = len(set(
            m["agent_id"] for m in delegated_missions
        ))
        goal_plan.metadata["delegated"] = True

        if parallel and len(delegated_missions) > 1:
            results = await self._execute_parallel(delegated_missions)
        else:
            results = []
            for m in delegated_missions:
                r = await self._execute_single_mission(m)
                results.append(r)

        success = all(r.get("success", False) for r in results)
        goal_plan.status = "completed" if success else "failed"

        return {
            "status": goal_plan.status,
            "goal_plan_id": goal_plan.goal_id,
            "objective": objective,
            "missions": results,
            "metrics": self._metrics.get_summary(),
        }

    def _select_agent_for_capability(self, capability: str) -> Any:
        cap_to_agent = {
            "task_decomposition": "planner-agent",
            "dependency_analysis": "planner-agent",
            "resource_allocation": "planner-agent",
            "priority_assignment": "planner-agent",
            "web_search": "research-agent",
            "knowledge_retrieval": "research-agent",
            "information_synthesis": "research-agent",
            "source_verification": "research-agent",
            "memory_storage": "memory-agent",
            "memory_retrieval": "memory-agent",
            "context_maintenance": "memory-agent",
            "summarization": "memory-agent",
            "code_generation": "code-agent",
            "code_review": "code-agent",
            "code_execution": "code-agent",
            "dependency_management": "code-agent",
            "web_navigation": "browser-agent",
            "content_extraction": "browser-agent",
            "form_interaction": "browser-agent",
            "screenshot_capture": "browser-agent",
            "tool_execution": "tool-agent",
            "tool_discovery": "tool-agent",
            "workflow_execution": "tool-agent",
            "result_processing": "tool-agent",
            "mission_planning": "mission-agent",
            "mission_monitoring": "mission-agent",
            "mission_recovery": "mission-agent",
            "agent_orchestration": "mission-agent",
        }
        agent_id = cap_to_agent.get(capability, "tool-agent")
        agent = self._agent_manager.get_agent(agent_id)
        if agent is None:
            agents = self._agent_manager.find_by_capability(capability)
            if agents:
                agent = agents[0]
        return agent

    def _create_agent_mission(self, goal_id: str, name: str,
                               capability: str, agent: Any,
                               sub_goal: dict) -> Dict[str, Any]:
        mission_id = str(uuid.uuid4())
        agent_id = agent.agent_id if agent else "tool-agent"
        self._mission_agent_map[mission_id] = agent_id
        if agent_id not in self._agent_mission_map:
            self._agent_mission_map[agent_id] = []
        self._agent_mission_map[agent_id].append(mission_id)

        self._publish(AgentMissionDelegated(
            mission_id=mission_id,
            goal_plan_id=goal_id,
            agent_id=agent_id,
            capability=capability,
        ))

        return {
            "mission_id": mission_id,
            "name": name,
            "capability": capability,
            "agent_id": agent_id,
            "sub_goal": sub_goal,
            "goal_id": goal_id,
        }

    async def _execute_single_mission(self, mission_def: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        agent_id = mission_def["agent_id"]
        capability = mission_def["capability"]
        mission_id = mission_def["mission_id"]
        goal_id = mission_def["goal_id"]

        agent = self._agent_manager.get_agent(agent_id)
        if agent is None:
            self._metrics.record_agent_task(agent_id, "unknown", False, 0)
            self._metrics.record_delegation(
                mission_id, agent_id, capability, False, 0,
            )
            return {
                "mission_id": mission_id,
                "success": False,
                "error": f"Agent '{agent_id}' not found",
            }

        self._agent_manager.transition_agent(agent_id, AgentState.RUNNING)

        ctx = self._shared_contexts.get(goal_id)
        if ctx:
            self._agent_manager.assign_mission(
                agent_id, mission_id, mission_def.get("name", ""),
            )

        task_handler = self._get_task_handler(capability)
        if task_handler:
            try:
                result = await task_handler(agent, mission_def, ctx)
                duration_ms = (time.time() - t0) * 1000
                self._metrics.record_agent_task(agent_id, agent.role, True, duration_ms)
                self._metrics.record_delegation(
                    mission_id, agent_id, capability, True, duration_ms,
                )
                self._agent_manager.transition_agent(agent_id, AgentState.IDLE)
                self._publish(AgentMissionCompleted(
                    mission_id=mission_id, agent_id=agent_id, success=True,
                ))
                return {
                    "mission_id": mission_id,
                    "success": True,
                    "agent_id": agent_id,
                    "duration_ms": duration_ms,
                    "result": result,
                }
            except Exception as e:
                duration_ms = (time.time() - t0) * 1000
                self._metrics.record_agent_task(agent_id, agent.role, False, duration_ms)
                self._metrics.record_delegation(
                    mission_id, agent_id, capability, False, duration_ms,
                )
                self._agent_manager.transition_agent(agent_id, AgentState.FAILED)
                self._publish(AgentMissionFailed(
                    mission_id=mission_id, agent_id=agent_id, error=str(e),
                ))
                return {
                    "mission_id": mission_id,
                    "success": False,
                    "agent_id": agent_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }

        self._agent_manager.transition_agent(agent_id, AgentState.IDLE)
        return {
            "mission_id": mission_id,
            "success": True,
            "agent_id": agent_id,
            "note": f"No handler for capability '{capability}'",
        }

    async def _execute_parallel(self, mission_defs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        t0 = time.time()
        groups = self._group_independent_missions(mission_defs)
        results = []

        for group in groups:
            if len(group) == 1:
                r = await self._execute_single_mission(group[0])
                results.append(r)
            else:
                tasks = [self._execute_single_mission(m) for m in group]
                parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
                for pr in parallel_results:
                    if isinstance(pr, Exception):
                        results.append({"success": False, "error": str(pr)})
                    else:
                        results.append(pr)

        parallel_ms = (time.time() - t0) * 1000
        sequential_ms = sum(r.get("duration_ms", 0) for r in results if isinstance(r, dict))
        self._metrics.record_parallel_run(sequential_ms, parallel_ms)

        return results

    def _group_independent_missions(self, mission_defs: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        if not mission_defs:
            return []

        agent_assignments = {}
        for m in mission_defs:
            aid = m.get("agent_id", "")
            if aid not in agent_assignments:
                agent_assignments[aid] = []
            agent_assignments[aid].append(m)

        groups = []
        current_group = []
        seen_agents: Set[str] = set()

        for m in mission_defs:
            aid = m.get("agent_id", "")
            if aid in seen_agents:
                if current_group:
                    groups.append(current_group)
                current_group = [m]
                seen_agents = {aid}
            else:
                current_group.append(m)
                seen_agents.add(aid)

        if current_group:
            groups.append(current_group)

        return groups

    def _get_task_handler(self, capability: str):
        handlers = {
            "web_search": self._handle_research_task,
            "knowledge_retrieval": self._handle_research_task,
            "information_synthesis": self._handle_research_task,
            "code_generation": self._handle_code_task,
            "code_review": self._handle_code_task,
            "code_execution": self._handle_code_task,
            "tool_execution": self._handle_tool_task,
            "workflow_execution": self._handle_tool_task,
            "memory_storage": self._handle_memory_task,
            "memory_retrieval": self._handle_memory_task,
            "summarization": self._handle_memory_task,
        }
        return handlers.get(capability)

    async def _handle_research_task(self, agent: Any,
                                     mission_def: Dict[str, Any],
                                     ctx: Optional[SharedMissionContext]) -> Dict[str, Any]:
        logger.info(f"Research task handled by {agent.agent_id}")
        return {"status": "research_completed", "findings": []}

    async def _handle_code_task(self, agent: Any,
                                 mission_def: Dict[str, Any],
                                 ctx: Optional[SharedMissionContext]) -> Dict[str, Any]:
        logger.info(f"Code task handled by {agent.agent_id}")
        return {"status": "code_completed", "artifacts": []}

    async def _handle_tool_task(self, agent: Any,
                                 mission_def: Dict[str, Any],
                                 ctx: Optional[SharedMissionContext]) -> Dict[str, Any]:
        logger.info(f"Tool task handled by {agent.agent_id}")
        return {"status": "tool_execution_completed"}

    async def _handle_memory_task(self, agent: Any,
                                   mission_def: Dict[str, Any],
                                   ctx: Optional[SharedMissionContext]) -> Dict[str, Any]:
        logger.info(f"Memory task handled by {agent.agent_id}")
        return {"status": "memory_operation_completed"}

    async def pause_mission(self, mission_id: str) -> bool:
        self._human_oversight.interrupt_mission(mission_id)
        if self._mission_executor:
            from app.mission_engine.base import MissionState
            result = await self._mission_executor.pause_mission(mission_id)
            return result.status == MissionState.PAUSED
        return True

    async def resume_mission(self, mission_id: str) -> bool:
        self._human_oversight.resume_mission(mission_id)
        if self._mission_executor:
            from app.mission_engine.base import MissionState
            result = await self._mission_executor.resume_mission(mission_id)
            return result.status == MissionState.RUNNING
        return True

    async def cancel_mission(self, mission_id: str) -> bool:
        if self._mission_executor:
            from app.mission_engine.base import MissionState
            result = await self._mission_executor.cancel_mission(mission_id)
            return result.status == MissionState.CANCELLED
        return True

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        agent = self._agent_manager.get_agent(agent_id)
        if not agent:
            return None
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "state": agent.state.value,
            "capabilities": [c.name for c in agent.capabilities],
            "current_mission": agent.mission.mission_id if agent.mission else None,
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        return [self.get_agent_status(a.agent_id)
                for a in self._agent_manager.list_agents()
                if self.get_agent_status(a.agent_id)]

    def get_shared_context(self, mission_id: str) -> Optional[SharedMissionContext]:
        return self._shared_contexts.get(mission_id)

    def get_metrics(self) -> AgentMissionMetrics:
        return self._metrics

    def get_human_oversight(self) -> HumanOversightManager:
        return self._human_oversight

    def health(self) -> Dict[str, Any]:
        agents = self._agent_manager.list_agents()
        return {
            "status": "HEALTHY",
            "agents_registered": len(agents),
            "agents_by_state": {
                state.value: sum(1 for a in agents if a.state == state)
                for state in AgentState
            },
            "active_shared_contexts": len(self._shared_contexts),
            "pending_approvals": len(self._human_oversight.list_pending()),
            "metrics": self._metrics.get_summary(),
        }

    def _publish(self, event: FridayEvent) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
