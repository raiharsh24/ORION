import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Set, Callable
from loguru import logger

from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.agent_framework.agent import create_all_builtin_agents, BUILTIN_AGENTS
from app.agent_framework.state import AgentState
from app.agent_framework.base import AgentCapability, AgentModel
from app.agent_orchestration.shared_context import SharedMissionContext
from app.agent_orchestration.metrics import AgentMissionMetrics
from app.agent_orchestration.events import (
    AgentMissionDelegated, AgentMissionCompleted, AgentMissionFailed,
    AgentAssistanceRequested, AgentFindingsPublished,
)
from app.agent_orchestration.human_oversight import HumanOversightManager
from app.agent_orchestration.orchestrator import AgentOrchestrator
from app.tool_selection.base import ToolSelectionResult, SelectedTool, ToolSelectionContext
from app.tool_execution.base import ExecutionMode
from app.tool_execution.executor import ToolExecutionEngine
from app.cognitive.events import MissionDelegated, MissionRecovered


class ReviewerAgent:
    ROLE = "reviewer"
    CAPABILITIES = [
        AgentCapability(name="code_review", description="Review code quality and correctness"),
        AgentCapability(name="design_review", description="Review architecture design"),
        AgentCapability(name="test_review", description="Review test coverage and quality"),
        AgentCapability(name="compliance_check", description="Check compliance with standards"),
    ]
    TOOLS = ["knowledge.search", "memory"]

    @staticmethod
    def create(agent_id: str = "reviewer-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Reviewer Agent",
            role=ReviewerAgent.ROLE,
            capabilities=ReviewerAgent.CAPABILITIES,
            tools=ReviewerAgent.TOOLS,
            permissions=["knowledge:read", "memory:read"],
            priority=7,
            memory_scope="session",
        )


class TesterAgent:
    ROLE = "tester"
    CAPABILITIES = [
        AgentCapability(name="test_execution", description="Execute test suites"),
        AgentCapability(name="test_generation", description="Generate test cases"),
        AgentCapability(name="regression_testing", description="Run regression tests"),
        AgentCapability(name="performance_testing", description="Run performance benchmarks"),
    ]
    TOOLS = ["terminal", "filesystem"]

    @staticmethod
    def create(agent_id: str = "tester-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Tester Agent",
            role=TesterAgent.ROLE,
            capabilities=TesterAgent.CAPABILITIES,
            tools=TesterAgent.TOOLS,
            permissions=["terminal:execute", "filesystem:read", "filesystem:write"],
            priority=6,
            memory_scope="session",
        )


COLLABORATIVE_AGENTS = {
    "reviewer-agent": ReviewerAgent,
    "tester-agent": TesterAgent,
}


class CollaborativeOrchestrator(AgentOrchestrator):
    TOOL_CAPABILITY_MAP: Dict[str, str] = {
        "web_search": "knowledge.search",
        "knowledge_retrieval": "knowledge.search",
        "information_synthesis": "knowledge.search",
        "code_generation": "code.execute",
        "code_review": "code.execute",
        "code_execution": "code.execute",
        "tool_execution": "tool.execute",
        "workflow_execution": "tool.execute",
        "memory_storage": "memory.store",
        "memory_retrieval": "memory.retrieve",
        "summarization": "llm.prompt",
    }

    def __init__(self, agent_manager: Any = None,
                 goal_planner: Any = None,
                 mission_executor: Any = None,
                 event_bus: Optional[EventBus] = None,
                 knowledge_graph: Any = None,
                 episodic_memory: Any = None,
                 hierarchical_goal_manager: Any = None,
                 adaptive_learning: Any = None,
                 reflection_v2: Any = None,
                 autonomous_scheduler: Any = None,
                 tool_execution_engine: Optional[ToolExecutionEngine] = None) -> None:
        super().__init__(
            agent_manager=agent_manager,
            goal_planner=goal_planner,
            mission_executor=mission_executor,
            event_bus=event_bus,
            knowledge_graph=knowledge_graph,
            episodic_memory=episodic_memory,
        )
        self._tool_execution_engine = tool_execution_engine
        self._hgm = hierarchical_goal_manager
        self._adaptive_learning = adaptive_learning
        self._reflection_v2 = reflection_v2
        self._autonomous_scheduler = autonomous_scheduler
        self._collaborative_results: Dict[str, Dict[str, Any]] = {}

        self._register_collaborative_agents()
        self._subscribe_collaborative_events()

    async def _execute_single_mission(self, mission_def: Dict[str, Any]) -> Dict[str, Any]:
        capability = mission_def.get("capability", "")
        tool_id = self.TOOL_CAPABILITY_MAP.get(capability)

        if self._tool_execution_engine and tool_id:
            from app.tools.base import ToolDefinition, ToolCategory, PermissionLevel
            td = ToolDefinition(
                id=tool_id, name=tool_id,
                description=mission_def.get("name", tool_id),
                category=ToolCategory.KNOWLEDGE,
            )
            sel = ToolSelectionResult(selected_tools=[
                SelectedTool(tool=td, score=1.0, selection_reason="cognitive_routing"),
            ])
            try:
                tool_result = await self._tool_execution_engine.execute(
                    selection_result=sel,
                    args_overrides={tool_id: mission_def.get("sub_goal", {})},
                    mode=ExecutionMode.SEQUENTIAL,
                    global_timeout=120.0,
                )
                if tool_result.all_succeeded:
                    return {
                        "mission_id": mission_def["mission_id"],
                        "success": True,
                        "agent_id": mission_def.get("agent_id", ""),
                        "duration_ms": sum(r.duration_ms for r in tool_result.results),
                        "result": {
                            "outputs": [
                                {"tool_id": r.tool_id, "output": r.output}
                                for r in tool_result.results
                            ],
                        },
                    }
                errors = [r.error for r in tool_result.results if r.error]
                return {
                    "mission_id": mission_def["mission_id"],
                    "success": False,
                    "agent_id": mission_def.get("agent_id", ""),
                    "error": "; ".join(errors) if errors else "Tool execution failed",
                }
            except Exception as e:
                return {
                    "mission_id": mission_def["mission_id"],
                    "success": False,
                    "agent_id": mission_def.get("agent_id", ""),
                    "error": str(e),
                }

        return await super()._execute_single_mission(mission_def)

    def _register_collaborative_agents(self) -> None:
        for factory in COLLABORATIVE_AGENTS.values():
            agent = factory.create()
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
            f"CollaborativeOrchestrator: Registered {len(COLLABORATIVE_AGENTS)} "
            f"collaborative agents"
        )

    def _subscribe_collaborative_events(self) -> None:
        if not self._event_bus:
            return
        self._event_bus.subscribe(
            "agent.collaboration.artifact_ready", self._on_artifact_ready
        )
        self._event_bus.subscribe(
            "agent.collaboration.review_complete", self._on_review_complete
        )
        self._event_bus.subscribe(
            "agent.collaboration.test_complete", self._on_test_complete
        )

    async def _on_artifact_ready(self, event: FridayEvent) -> None:
        mission_id = event.data.get("mission_id", "")
        ctx = self._shared_contexts.get(mission_id)
        if ctx:
            ctx.write_shared("artifact_ready", event.data, writer="collaboration")

    async def _on_review_complete(self, event: FridayEvent) -> None:
        mission_id = event.data.get("mission_id", "")
        ctx = self._shared_contexts.get(mission_id)
        if ctx:
            ctx.write_shared("review_result", event.data, writer="collaboration")

    async def _on_test_complete(self, event: FridayEvent) -> None:
        mission_id = event.data.get("mission_id", "")
        ctx = self._shared_contexts.get(mission_id)
        if ctx:
            ctx.write_shared("test_result", event.data, writer="collaboration")

    async def collaborative_workflow(self, objective: str,
                                     description: str = "",
                                     require_approval: bool = False,
                                     workflow_type: str = "research_code_review_test",
                                     use_mission_executor: bool = False,
                                     ) -> Dict[str, Any]:
        goal_id = str(uuid.uuid4())

        if use_mission_executor and self._mission_executor:
            return await self._run_via_mission_executor(
                objective=objective, description=description,
                workflow_type=workflow_type, goal_id=goal_id,
            )

        ctx = SharedMissionContext(
            mission_id=goal_id,
            knowledge_graph=self._knowledge_graph,
            episodic_memory=self._episodic_memory,
        )
        self._shared_contexts[goal_id] = ctx

        workflow_steps = self._build_workflow_steps(workflow_type)
        results: List[Dict[str, Any]] = []

        agent_ids = list(dict.fromkeys(s["agent_id"] for s in workflow_steps))
        self._publish(MissionDelegated(
            mission_id=goal_id, objective=objective,
            workflow_type=workflow_type, agent_ids=agent_ids,
        ))

        for step in workflow_steps:
            agent = self._get_or_create_agent(step["agent_id"], step["role"])
            if not agent:
                results.append({
                    "step": step["name"], "success": False,
                    "error": f"Agent '{step['agent_id']}' unavailable",
                })
                continue

            mis_def = {
                "mission_id": str(uuid.uuid4()),
                "name": step["name"],
                "capability": step["capability"],
                "agent_id": step["agent_id"],
                "sub_goal": {"name": step["name"], "capability": step["capability"]},
                "goal_id": goal_id,
            }
            self._mission_agent_map[mis_def["mission_id"]] = step["agent_id"]

            self._publish(AgentMissionDelegated(
                mission_id=mis_def["mission_id"],
                goal_plan_id=goal_id,
                agent_id=step["agent_id"],
                capability=step["capability"],
            ))

            result = await self._execute_single_mission(mis_def)
            results.append({
                "step": step["name"],
                "agent_id": step["agent_id"],
                "capability": step["capability"],
                **result,
            })

            if not result.get("success") and step.get("required", True):
                break

        success = all(r.get("success", False) for r in results)
        self._collaborative_results[goal_id] = {
            "status": "completed" if success else "failed",
            "results": results,
        }

        if self._hgm:
            parent_goal = self._hgm.create_hierarchy(
                objective=objective, description=description,
            )
            for r in results:
                g = self._hgm.add_sub_goal(
                    hierarchy_id=parent_goal.root_id,
                    parent_id=parent_goal.root_id,
                    objective=f"{r.get('step', 'step')}: {r.get('capability', '')}",
                )
                if g:
                    self._hgm.update_goal_status(
                        parent_goal.root_id, g.goal_id,
                        "completed" if r.get("success") else "failed",
                    )

        return {
            "status": "completed" if success else "failed",
            "goal_id": goal_id,
            "objective": objective,
            "workflow_type": workflow_type,
            "results": results,
        }

    async def _run_via_mission_executor(
        self, objective: str, description: str,
        workflow_type: str, goal_id: str,
    ) -> Dict[str, Any]:
        from app.workflow_engine.base import WorkflowStep, WorkflowGraph, WorkflowStatus
        from app.mission_engine.base import MissionState

        steps = self._build_workflow_steps(workflow_type)
        graph_steps = []
        for i, s in enumerate(steps):
            graph_steps.append(WorkflowStep(
                id=f"{goal_id}_{i}",
                node_id=s["agent_id"],
                step_type="tool_execution",
                config={
                    "capability": s["capability"],
                    "agent_id": s["agent_id"],
                    "name": s["name"],
                },
            ))

        graph = WorkflowGraph(
            workflow_id=f"cognitive_{goal_id[:8]}",
            steps=graph_steps,
        )

        try:
            self._mission_executor.register_workflow_graph(graph.workflow_id, graph)
            mission = self._mission_executor.create_mission(
                name=objective[:80],
                description=description,
                workflow_graphs={graph.workflow_id: graph},
                metadata={"source": "cognitive", "goal_id": goal_id},
            )
            result = await self._mission_executor.start_mission(mission.id)

            wf_results = {}
            for wf_id, wf_out in result.workflow_results.items():
                if isinstance(wf_out, dict):
                    wf_results[str(wf_id)] = wf_out

            success = result.status == MissionState.COMPLETED
            return {
                "status": "completed" if success else "failed",
                "goal_id": goal_id,
                "objective": objective,
                "workflow_type": workflow_type,
                "mission_id": mission.id,
                "results": [
                    {"step": s["name"], "success": True,
                     "agent_id": s["agent_id"], "capability": s["capability"]}
                    for s in steps
                ] if success else [],
            }
        except Exception as e:
            return {
                "status": "failed", "goal_id": goal_id,
                "objective": objective, "workflow_type": workflow_type,
                "error": str(e),
            }

    def _build_workflow_steps(self, workflow_type: str) -> List[Dict[str, Any]]:
        templates = {
            "research_code_review_test": [
                {"name": "Research", "role": "research",
                 "agent_id": "research-agent", "capability": "information_synthesis"},
                {"name": "Plan Architecture", "role": "planner",
                 "agent_id": "planner-agent", "capability": "task_decomposition"},
                {"name": "Implement Code", "role": "code",
                 "agent_id": "code-agent", "capability": "code_generation"},
                {"name": "Review Code", "role": "reviewer",
                 "agent_id": "reviewer-agent", "capability": "code_review"},
                {"name": "Test Implementation", "role": "tester",
                 "agent_id": "tester-agent", "capability": "test_execution"},
                {"name": "Store Results", "role": "memory",
                 "agent_id": "memory-agent", "capability": "memory_storage"},
            ],
            "plan_code_test": [
                {"name": "Plan", "role": "planner",
                 "agent_id": "planner-agent", "capability": "task_decomposition"},
                {"name": "Implement", "role": "code",
                 "agent_id": "code-agent", "capability": "code_generation"},
                {"name": "Test", "role": "tester",
                 "agent_id": "tester-agent", "capability": "test_execution"},
            ],
            "research_synthesize": [
                {"name": "Research", "role": "research",
                 "agent_id": "research-agent", "capability": "web_search"},
                {"name": "Analyze", "role": "research",
                 "agent_id": "research-agent", "capability": "information_synthesis"},
                {"name": "Store Findings", "role": "memory",
                 "agent_id": "memory-agent", "capability": "memory_storage"},
            ],
        }
        return templates.get(workflow_type, templates["research_code_review_test"])

    def _get_or_create_agent(self, agent_id: str, role: str) -> Any:
        agent = self._agent_manager.get_agent(agent_id)
        if agent:
            return agent
        factories = {
            "reviewer": ReviewerAgent,
            "tester": TesterAgent,
        }
        factory = factories.get(role)
        if factory:
            model = factory.create(agent_id=agent_id)
            self._agent_manager.create_agent(
                agent_id=model.agent_id,
                name=model.name,
                role=model.role,
                capabilities=[c.name for c in model.capabilities],
                tools=model.tools,
                permissions=model.permissions,
                priority=model.priority,
            )
            return self._agent_manager.get_agent(agent_id)
        return None

    async def schedule_goal(self, objective: str,
                             delay_seconds: float = 0.0,
                             priority: float = 5.0,
                             recurring: bool = False,
                             interval_seconds: float = 0.0) -> Dict[str, Any]:
        if not self._autonomous_scheduler:
            return {"status": "error", "error": "No autonomous scheduler available"}

        if recurring and interval_seconds > 0:
            mission = self._autonomous_scheduler.schedule_recurring(
                objective=objective,
                interval_seconds=interval_seconds,
                priority=priority,
            )
        else:
            mission = self._autonomous_scheduler.schedule_once(
                objective=objective,
                delay_seconds=delay_seconds,
                priority=priority,
            )
        return {
            "status": "scheduled",
            "mission_id": mission.mission_id,
            "objective": objective,
            "scheduled_at": mission.scheduled_at,
        }

    def get_collaborative_result(self, goal_id: str) -> Optional[Dict[str, Any]]:
        return self._collaborative_results.get(goal_id)

    def get_collaboration_summary(self) -> Dict[str, Any]:
        total = len(self._collaborative_results)
        successful = sum(
            1 for r in self._collaborative_results.values()
            if r.get("status") == "completed"
        )
        return {
            "total_collaborations": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(successful / total, 3) if total > 0 else 0.0,
        }

    async def run_cognitive_mission(self, objective: str,
                                     description: str = "",
                                     require_approval: bool = False,
                                     use_hierarchy: bool = True,
                                     use_collaboration: bool = True,
                                     use_scheduler: bool = False,
                                     delay_seconds: float = 0.0,
                                     use_mission_executor: bool = False) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "objective": objective,
            "hierarchy": None,
            "collaboration": None,
        }

        if use_hierarchy and self._hgm:
            hierarchy = self._hgm.analyze_and_decompose(objective, description)
            result["hierarchy"] = {
                "root_id": hierarchy.root_id,
                "node_count": len(hierarchy.nodes),
                "depth": hierarchy.depth,
            }

        if use_collaboration:
            collab = await self.collaborative_workflow(
                objective=objective,
                description=description,
                require_approval=require_approval,
                use_mission_executor=use_mission_executor,
            )
            result["collaboration"] = collab

            if self._reflection_v2 and collab.get("goal_id"):
                report = await self._reflection_v2.analyze(
                    mission_id=collab.get("goal_id", objective),
                    goal_id=(result["hierarchy"] or {}).get("root_id", ""),
                    execution_data={
                        "stages": [
                            {"status": "completed" if r.get("success") else "failed",
                             "duration_ms": r.get("duration_ms", 0)}
                            for r in collab.get("results", [])
                        ],
                        "retry_count": 0,
                        "recovery_count": 0,
                        "errors": [
                            r.get("error", "") for r in collab.get("results", [])
                            if not r.get("success")
                        ],
                        "failures": [
                            {"stage": r.get("step", ""), "error": r.get("error", ""),
                             "category": "execution"}
                            for r in collab.get("results", []) if not r.get("success")
                        ],
                        "successes": [
                            {"description": f"{r.get('step', '')} completed",
                             "category": r.get("capability", "general"),
                             "effectiveness": 1.0}
                            for r in collab.get("results", []) if r.get("success")
                        ],
                    },
                )
                result["reflection"] = {
                    "reflection_id": report.reflection_id,
                    "recommendations": report.recommendations,
                }

        if use_scheduler and delay_seconds > 0 and self._autonomous_scheduler:
            sched = await self.schedule_goal(
                objective=objective,
                delay_seconds=delay_seconds,
            )
            result["scheduled"] = sched

        all_success = True
        if result.get("collaboration"):
            all_success = result["collaboration"].get("status") == "completed"

        result["status"] = "completed" if all_success else "failed"
        return result

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        agent = self._agent_manager.get_agent(agent_id)
        if not agent:
            return None
        reliability = None
        if self._adaptive_learning:
            reliability = self._adaptive_learning.get_agent_reliability(agent_id)
        base = super().get_agent_status(agent_id)
        if base and reliability:
            base["reliability"] = reliability
        return base

    def health(self) -> Dict[str, Any]:
        base = super().health()
        base["collaborative_workflows"] = len(self._collaborative_results)
        if self._autonomous_scheduler:
            base["scheduler_stats"] = self._autonomous_scheduler.get_stats()
        if self._adaptive_learning:
            base["adaptive_learning"] = self._adaptive_learning.get_summary()
        return base
