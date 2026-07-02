import time
import uuid
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone

from app.runtime.base import Mission, MissionStage, ExecutionResult
from app.runtime.state import MissionStateMachine
from app.runtime.dispatcher import Dispatcher
from app.runtime.executor import MissionExecutor
from app.runtime.supervisor import Supervisor
from app.runtime.reflection import ReflectionEngine
from app.runtime.telemetry import TelemetryCollector
from app.runtime.metrics import RuntimeMetrics
from app.runtime.events import (
    MissionStarted, MissionPaused, MissionResumed,
    MissionCompleted, MissionFailed, MissionRecovered, MissionArchived,
)
from app.runtime.persistence import MissionStore


class Orchestrator:
    def __init__(self, agent_manager: Any = None,
                 planning_engine: Any = None,
                 workflow_engine: Any = None,
                 tool_execution_engine: Any = None,
                 tool_selection_engine: Any = None,
                 capability_resolver: Any = None,
                 capability_registry: Any = None,
                 plugin_runtime: Any = None,
                 memory_engine: Any = None,
                 store: Optional[MissionStore] = None):
        self._agent_manager = agent_manager
        self._planning_engine = planning_engine
        self._workflow_engine = workflow_engine
        self._tool_execution_engine = tool_execution_engine
        self._tool_selection_engine = tool_selection_engine
        self._capability_resolver = capability_resolver
        self._capability_registry = capability_registry
        self._plugin_runtime = plugin_runtime
        self._memory_engine = memory_engine
        self._store = store or MissionStore()
        self._event_bus = None

        self._dispatcher = Dispatcher(
            agent_manager=agent_manager,
            workflow_engine=workflow_engine,
            tool_executor=tool_execution_engine,
            plugin_runtime=plugin_runtime,
        )
        self._executor = MissionExecutor(
            agent_manager=agent_manager,
            workflow_engine=workflow_engine,
            tool_execution_engine=tool_execution_engine,
            plugin_runtime=plugin_runtime,
            dispatcher=self._dispatcher,
        )
        self._supervisor = Supervisor(
            agent_manager=agent_manager,
            executor=self._executor,
        )
        self._reflection = ReflectionEngine(plan_memory=planning_engine)
        self._telemetry = TelemetryCollector()
        self._metrics = RuntimeMetrics()
        self._missions: Dict[str, Mission] = {}
        self._on_mission_hooks: List[Callable] = []

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    def on_mission(self, hook: Callable) -> None:
        self._on_mission_hooks.append(hook)

    async def submit_request(self, user_request: str,
                              intent: str = "",
                              metadata: Optional[Dict[str, Any]] = None
                              ) -> Mission:
        mission_id = str(uuid.uuid4())
        mission = Mission(
            mission_id=mission_id,
            user_request=user_request,
            intent=intent,
            status="created",
            metadata=metadata or {},
        )
        self._missions[mission_id] = mission
        self._executor.register_mission(mission)
        self._telemetry.create_mission(mission_id, intent)
        self._metrics.record_mission_created()
        self._store.save_mission(mission)

        self._publish_event(MissionStarted(mission_id, user_request, intent))
        return mission

    async def run_lifecycle(self, mission: Mission) -> ExecutionResult:
        mission.set_status("planning")
        planning_stage = mission.add_stage("planning")
        plan = await self._run_planning(mission)
        planning_stage.completed_at = datetime.now(timezone.utc)
        planning_stage.status = "completed" if plan is not None else "failed"
        if plan is None:
            planning_stage.error = "Planning failed — no plan generated"

        mission.add_stage("capability_resolution")
        capabilities = await self._run_capability_resolution(mission, plan)
        if capabilities:
            mission.complete_stage("capability_resolution")
        else:
            mission.complete_stage("capability_resolution",
                                    error="No capabilities resolved")

        mission.add_stage("tool_selection")
        selection_result = await self._run_tool_selection(mission, capabilities)
        if selection_result is not None:
            mission.complete_stage("tool_selection")
            tool_ids = getattr(selection_result, "tool_ids", [])
            if tool_ids:
                mission.metadata["tool_ids"] = tool_ids
        else:
            mission.complete_stage("tool_selection",
                                    error="No tools selected")

        mission.add_stage("workflow_generation")
        workflow_graph = await self._run_workflow_generation(mission, plan, capabilities)
        if workflow_graph is not None:
            mission.complete_stage("workflow_generation")
            mission.metadata["workflow_graph_id"] = getattr(workflow_graph, "execution_id", None)
        else:
            mission.complete_stage("workflow_generation",
                                    error="No workflow generated")

        execution_stage = mission.add_stage("execution")
        result = await self._executor.execute_mission(
            mission, plan=plan, selection_result=selection_result,
        )
        if result.success:
            mission.complete_stage("execution")
        else:
            mission.complete_stage("execution", error=result.error)

        if not result.success:
            self._supervisor.record_failure(mission.mission_id)
            recovery_action = await self._supervisor.recover_failure(
                mission.mission_id, result.error or "Unknown error",
            )
            if recovery_action.status == "completed":
                self._telemetry.record_recovery(mission.mission_id)
                self._metrics.record_recovery()
                self._publish_event(MissionRecovered(
                    mission.mission_id,
                    self._supervisor.recovery_count,
                ))

        mission.add_stage("reflection")
        tel = self._telemetry.get_mission(mission.mission_id)
        report = await self._reflection.reflect(mission, result, tel)
        mission.complete_stage("reflection")
        if report.bottlenecks:
            mission.metadata["bottlenecks"] = report.bottlenecks
        if report.lessons:
            mission.metadata["lessons"] = [
                {"category": l.category, "description": l.description,
                 "severity": l.severity, "recommendation": l.recommendation}
                for l in report.lessons
            ]

        mission.add_stage("memory_update")
        await self._run_memory_update(mission, report)
        mission.complete_stage("memory_update")

        if result.success:
            mission.set_status("completed")
            self._metrics.record_mission_completed()
            self._publish_event(MissionCompleted(
                mission.mission_id, result.total_duration_ms,
                result.stages_completed,
            ))
        else:
            mission.set_status("failed")
            self._metrics.record_mission_failed()
            self._publish_event(MissionFailed(
                mission.mission_id, "execution", result.error or "Unknown",
            ))

        self._telemetry.record_completion(
            mission.mission_id, result.success, result.total_duration_ms)
        self._metrics.record_duration(result.total_duration_ms)
        self._store.save_mission(mission)
        self._store.save_telemetry(mission.mission_id,
                                    self._telemetry.get_mission(mission.mission_id))
        self._store.save_reflection(mission.mission_id, report)

        for hook in self._on_mission_hooks:
            try:
                hook(mission, result)
            except Exception:
                pass

        return result

    async def _run_planning(self, mission: Mission) -> Any:
        planning_start = time.time()
        if not self._planning_engine:
            return None
        try:
            has_create = hasattr(self._planning_engine, "create_goal")
            has_generate = hasattr(self._planning_engine, "generate_plan")
            if not has_create or not has_generate:
                return None

            goal_name = mission.intent or mission.user_request[:50]
            required_capabilities = list(mission.metadata.get("required_capabilities", []))
            goal = self._planning_engine.create_goal(
                name=goal_name,
                description=mission.user_request,
                required_capabilities=required_capabilities or None,
            )
            if goal:
                goal_id = getattr(goal, "goal_id", None)
                if goal_id:
                    mission.goal_ids.append(goal_id)

            plan = await self._planning_engine.generate_plan(goal)
            if plan:
                plan_id = getattr(plan, "plan_id", None)
                if plan_id:
                    mission.plan_id = plan_id
                mission.metadata["plan_steps"] = getattr(plan, "step_count", 0)
                mission.metadata["plan_duration"] = getattr(
                    plan, "total_duration", 0.0)

            elapsed = (time.time() - planning_start) * 1000
            self._telemetry.record_planning_latency(mission.mission_id, elapsed)
            self._metrics.record_planning_latency(elapsed)
            self._store.save_checkpoint(mission.mission_id, "planning",
                                         {"elapsed_ms": elapsed})
            return plan
        except Exception as e:
            elapsed = (time.time() - planning_start) * 1000
            self._telemetry.record_planning_latency(mission.mission_id, elapsed)
            self._telemetry.record_failure(mission.mission_id, "planning", str(e))
            mission.complete_stage("planning", error=str(e))
            return None

    async def _run_capability_resolution(self, mission: Mission,
                                          plan: Any) -> List[str]:
        start = time.time()
        capabilities: List[str] = []

        if plan and self._capability_resolver:
            try:
                plan_steps = getattr(plan, "steps", [])
                for step in plan_steps:
                    action_id = getattr(step, "action_id", "")
                    if action_id:
                        resolved = self._capability_resolver.resolve(action_id)
                        if resolved and not getattr(resolved, "errors", None):
                            tool_ids = getattr(resolved, "resolved_tool_ids", [])
                            capabilities.extend(tool_ids)
            except Exception:
                pass

        elif self._capability_registry:
            try:
                all_caps = None
                if hasattr(self._capability_registry, "list_capabilities"):
                    all_caps = self._capability_registry.list_capabilities()
                elif hasattr(self._capability_registry, "list_metadata"):
                    all_caps = self._capability_registry.list_metadata()
                if all_caps:
                    for c in all_caps:
                        cid = getattr(c, "id", None) or getattr(c, "capability_id", None)
                        cname = getattr(c, "name", None)
                        if cid and cid not in capabilities:
                            capabilities.append(cid)
                        elif cname and cname not in capabilities:
                            capabilities.append(cname)
            except Exception:
                pass

        if not capabilities and self._agent_manager:
            try:
                agents = (self._agent_manager.list_agents()
                          if hasattr(self._agent_manager, "list_agents") else [])
                for a in agents:
                    for c in (getattr(a, "capabilities", []) or []):
                        cap = c if isinstance(c, str) else getattr(c, "name", str(c))
                        if cap not in capabilities:
                            capabilities.append(cap)
            except Exception:
                pass

        elapsed = (time.time() - start) * 1000
        self._telemetry.record_resolution_latency(mission.mission_id, elapsed)
        mission.metadata["resolved_capabilities"] = capabilities
        self._store.save_checkpoint(mission.mission_id, "capability_resolution",
                                     {"capabilities": capabilities,
                                      "elapsed_ms": elapsed})
        return capabilities

    async def _run_tool_selection(self, mission: Mission,
                                   capabilities: List[str]) -> Any:
        start = time.time()
        if not self._tool_selection_engine or not capabilities:
            return None
        try:
            from app.tool_selection.base import ToolSelectionContext
            context = ToolSelectionContext(
                required_capabilities=capabilities,
            )
            intent = mission.intent
            if intent:
                from app.intent.types import IntentType
                try:
                    context.intent = IntentType(intent.upper())
                except (ValueError, AttributeError):
                    pass

            result = await self._tool_selection_engine.select(context)
            elapsed = (time.time() - start) * 1000
            self._telemetry.record_tool_latency(
                mission.mission_id, "tool_selection", elapsed)
            self._store.save_checkpoint(mission.mission_id, "tool_selection",
                                         {"selected": getattr(result, "tool_ids", []),
                                          "elapsed_ms": elapsed})
            return result
        except Exception:
            return None

    async def _run_workflow_generation(self, mission: Mission,
                                        plan: Any,
                                        capabilities: List[str]) -> Any:
        if not plan or not self._workflow_engine:
            return None
        try:
            from app.workflow_engine.base import WorkflowGraph, WorkflowNode, WorkflowNodeType
            graph = WorkflowGraph(
                entry_node_ids=[],
                metadata={"mission_id": mission.mission_id,
                          "user_request": mission.user_request},
            )
            plan_steps = getattr(plan, "steps", [])
            if plan_steps:
                prev_id = None
                for i, step in enumerate(plan_steps):
                    node_id = f"step_{i}"
                    action_id = getattr(step, "action_id", "plan")
                    node = WorkflowNode(
                        id=node_id,
                        name=getattr(step, "action_name", action_id),
                        node_type=WorkflowNodeType.TOOL,
                        tool_id=action_id or "plan",
                        timeout=float(getattr(step, "estimated_duration", 60) or 60) * 2,
                    )
                    graph.add_node(node)
                    if prev_id:
                        graph.add_edge(prev_id, node_id)
                    else:
                        graph.entry_node_ids.append(node_id)
                    prev_id = node_id

                if graph.node_count > 0:
                    exec_ctx = await self._workflow_engine.execute(graph)
                    return exec_ctx

            return None
        except Exception:
            return None

    async def _run_memory_update(self, mission: Mission,
                                  report: Any) -> None:
        if not self._memory_engine:
            return
        try:
            key = f"mission:{mission.mission_id}"
            value = {
                "request": mission.user_request,
                "intent": mission.intent,
                "status": mission.status,
                "duration_ms": mission.total_duration_ms,
            }
            if hasattr(report, "lessons"):
                value["lessons"] = [
                    {"category": l.category, "description": l.description}
                    for l in report.lessons
                ]

            if hasattr(self._memory_engine, "get_working_memory"):
                wm = self._memory_engine.get_working_memory()
                if hasattr(wm, "set"):
                    wm.set(key, value)

            if hasattr(self._memory_engine, "retrieve_relevant_context"):
                self._memory_engine.retrieve_relevant_context(
                    query=mission.user_request,
                    limit=1,
                )
        except Exception:
            pass

    async def pause_mission(self, mission_id: str) -> bool:
        result = await self._executor.pause_mission(mission_id)
        if result:
            self._publish_event(MissionPaused(mission_id))
            mission = self._missions.get(mission_id)
            if mission:
                self._store.save_mission(mission)
        return result

    async def resume_mission(self, mission_id: str) -> bool:
        result = await self._executor.resume_mission(mission_id)
        if result:
            self._publish_event(MissionResumed(mission_id))
            mission = self._missions.get(mission_id)
            if mission:
                self._store.save_mission(mission)
        return result

    async def cancel_mission(self, mission_id: str) -> bool:
        result = await self._executor.cancel_mission(mission_id)
        if result:
            mission = self._missions.get(mission_id)
            if mission:
                self._store.save_mission(mission)
        return result

    async def archive_mission(self, mission_id: str) -> bool:
        mission = self._missions.get(mission_id)
        if mission and mission.status in ("completed", "failed"):
            mission.set_status("archived")
            self._store.save_mission(mission)
            self._publish_event(MissionArchived(mission_id))
            return True
        return False

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self._missions.get(mission_id)

    def list_missions(self) -> List[Mission]:
        return list(self._missions.values())

    def list_active_missions(self) -> List[Mission]:
        return [m for m in self._missions.values()
                if m.status in ("planning", "ready", "running", "recovering")]

    @property
    def supervisor(self) -> Supervisor:
        return self._supervisor

    @property
    def telemetry(self) -> TelemetryCollector:
        return self._telemetry

    @property
    def metrics(self) -> RuntimeMetrics:
        return self._metrics

    def health(self) -> Dict[str, Any]:
        h = self._metrics.snapshot()
        missions = self.list_missions()
        return {
            "status": "healthy",
            "running_missions": sum(1 for m in missions if m.status == "running"),
            "queued_missions": sum(1 for m in missions
                                   if m.status in ("created", "planning", "ready")),
            "paused_missions": sum(1 for m in missions if m.status == "paused"),
            "completed_missions": sum(1 for m in missions if m.status == "completed"),
            "failed_missions": sum(1 for m in missions if m.status == "failed"),
            "total_missions": len(missions),
            "average_runtime_ms": h.average_duration_ms,
            "recovery_success_rate": round(
                self._supervisor.recovery_success_rate, 3),
            "dispatcher_available": self._dispatcher.available,
            "executor_available": self._executor.available,
            "supervisor_available": self._supervisor.available,
            "success_rate": h.success_rate,
            "total_retries": h.total_retries,
            "total_recoveries": h.total_recoveries,
            "mission_store_available": True,
        }

    def _publish_event(self, event: Any) -> None:
        if self._event_bus:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self._event_bus.publish(event))
            except RuntimeError:
                pass
