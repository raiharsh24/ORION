import asyncio
import time
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone
from loguru import logger

from app.events.bus import EventBus
from app.tool_execution.executor import CancellationToken
from app.workflow_engine.base import WorkflowGraph, WorkflowStatus, WorkflowContext
from app.workflow_engine.executor import WorkflowExecutor
from app.mission_engine.base import (
    Mission, MissionState, MissionPriority, MissionContext,
    MissionCheckpoint, MissionProgress, MissionResult, MissionTelemetry,
)
from app.mission_engine.events import (
    MissionCreated, MissionStarted, MissionProgressUpdated,
    MissionCheckpointSaved, MissionCompleted, MissionFailed, MissionCancelled,
)
from app.mission_engine.mission import MissionStore
from app.mission_engine.checkpoint import CheckpointManager
from app.mission_engine.result import build_mission_result
from app.mission_engine.planner import MissionPlanner
from app.runtime.scheduler import AdaptiveScheduler
from app.runtime.monitor import ExecutionMonitor


class MissionExecutor:
    def __init__(
        self,
        workflow_executor: WorkflowExecutor,
        store: MissionStore,
        checkpoint_manager: CheckpointManager,
        planner: MissionPlanner,
        event_bus: Optional[EventBus] = None,
        recovery_policies: Optional[Any] = None,
        scheduler: Optional[AdaptiveScheduler] = None,
        monitor: Optional[ExecutionMonitor] = None,
    ) -> None:
        self._workflow_executor = workflow_executor
        self._store = store
        self._checkpoints = checkpoint_manager
        self._planner = planner
        self._event_bus = event_bus
        self._recovery_policies = recovery_policies
        self._scheduler = scheduler
        self._monitor = monitor
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._workflow_graphs: Dict[str, WorkflowGraph] = {}
        self._cancellation_tokens: Dict[str, CancellationToken] = {}
        self._completed_workflows: Dict[str, Set[str]] = {}
        self._failed_workflows: Dict[str, Set[str]] = {}
        self._mission_contexts: Dict[str, MissionContext] = {}
        self._telemetry: Dict[str, MissionTelemetry] = {}
        self._execution_count = 0
        self._failure_count = 0
        self._total_latency_ms = 0.0
        self._revision_count = 0

    async def _try_revision(
        self,
        mission_id: str,
        failed_workflow_id: str,
        error: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Attempts dynamic plan revision when a workflow fails.

        Uses RecoveryPolicies if configured, otherwise returns None.
        Never restarts the whole mission — only re-plans remaining work.
        """
        if not self._recovery_policies:
            return None

        recovery_ctx = {
            "mission_id": mission_id,
            "workflow_id": failed_workflow_id,
            "error": error,
            "tool_name": (context or {}).get("tool_name", failed_workflow_id),
            "completed_workflows": list(self._completed_workflows.get(mission_id, set())),
            "failed_workflows": list(self._failed_workflows.get(mission_id, set())),
        }

        attempt = await self._recovery_policies.recover(mission_id, recovery_ctx)
        if attempt.success:
            self._revision_count += 1
            return {f"{failed_workflow_id}_retry": {
                "status": "recovered",
                "strategy": attempt.strategy,
            }}
        return None

    def register_workflow_graph(self, wf_id: str, graph: WorkflowGraph) -> None:
        self._workflow_graphs[wf_id] = graph

    def get_workflow_graph(self, wf_id: str) -> Optional[WorkflowGraph]:
        return self._workflow_graphs.get(wf_id)

    def get_mission_context(self, mission_id: str) -> Optional[MissionContext]:
        return self._mission_contexts.get(mission_id)

    def create_mission(
        self,
        name: str,
        description: str = "",
        workflow_graphs: Optional[Dict[str, WorkflowGraph]] = None,
        workflow_ids: Optional[List[str]] = None,
        priority: MissionPriority = MissionPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Mission:
        if workflow_graphs:
            for wf_id, graph in workflow_graphs.items():
                self.register_workflow_graph(wf_id, graph)
            used_wf_ids = list(workflow_graphs.keys())
        else:
            used_wf_ids = workflow_ids or []

        mission = self._planner.create_mission(
            name=name,
            description=description,
            workflow_ids=used_wf_ids,
            priority=priority,
            metadata=metadata,
        )

        self._completed_workflows[mission.id] = set()
        self._failed_workflows[mission.id] = set()
        self._mission_contexts[mission.id] = MissionContext(mission_id=mission.id)
        self._telemetry[mission.id] = MissionTelemetry()

        self._publish(MissionCreated(
            mission_id=mission.id,
            name=mission.name,
            total_workflows=len(mission.workflow_ids),
        ))
        return mission

    async def start_mission(
        self,
        mission_id: str,
        background: bool = False,
    ) -> MissionResult:
        mission = self._store.get(mission_id)
        if mission is None:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' not found",
                errors=[f"Mission '{mission_id}' not found"],
            )
        if mission.state.is_active:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' already running",
                errors=[f"Mission '{mission_id}' already running"],
            )
        if mission.state.is_terminal:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' already completed",
                errors=[f"Mission '{mission_id}' already completed"],
            )

        if background:
            task = asyncio.create_task(self._execute_mission(mission_id))
            self._running_tasks[mission_id] = task
            return MissionResult(
                mission_id=mission_id, status=MissionState.RUNNING,
                total_workflows=len(mission.workflow_ids),
            )

        return await self._execute_mission(mission_id)

    async def _execute_mission(self, mission_id: str) -> MissionResult:
        mission = self._store.get(mission_id)
        if mission is None:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' not found",
            )

        self._store.update_state(mission_id, MissionState.RUNNING)
        self._publish(MissionStarted(mission_id=mission_id, name=mission.name))

        token = CancellationToken()
        self._cancellation_tokens[mission_id] = token
        ctx = self._mission_contexts.get(mission_id) or MissionContext(mission_id=mission_id)
        t0 = time.time()

        workflow_order = self._planner.plan_sequential(mission, self._workflow_graphs)
        workflow_results: Dict[str, Any] = {}

        idx = 0
        try:
            while idx < len(workflow_order):
                if token.cancelled:
                    mission = self._store.get(mission_id)
                    if mission:
                        self._store.update_state(mission_id, MissionState.CANCELLED)
                    self._publish(MissionCancelled(
                        mission_id=mission_id, name=mission.name if mission else "",
                        reason="Cancelled during execution",
                        completed_workflows=len(self._completed_workflows[mission_id]),
                        total_workflows=len(mission.workflow_ids) if mission else 0,
                    ))
                    self._telemetry[mission_id].cancel_count += 1
                    return self._finalize(mission_id, MissionState.CANCELLED, workflow_results, ctx, t0)

                wf_id = workflow_order[idx]

                if mission_id in self._failed_workflows and wf_id in self._failed_workflows[mission_id]:
                    workflow_results[wf_id] = {"status": "skipped", "error": "Skipped due to prior failure"}
                    idx += 1
                    continue

                graph = self._workflow_graphs.get(wf_id)
                if graph is None:
                    workflow_results[wf_id] = {"status": "failed", "error": f"Workflow graph '{wf_id}' not registered"}
                    self._failed_workflows[mission_id].add(wf_id)
                    self._publish(MissionFailed(
                        mission_id=mission_id, name=mission.name,
                        error=f"Workflow '{wf_id}' graph not found",
                        completed_workflows=len(self._completed_workflows[mission_id]),
                        total_workflows=len(mission.workflow_ids),
                    ))

                    revision_result = await self._try_revision(mission_id, wf_id, "workflow_graph_not_found")
                    if revision_result:
                        workflow_results.update(revision_result)
                        idx += 1
                        continue
                    break

                wf_t0 = time.time()
                wf_result = await self._workflow_executor.execute(
                    graph=graph,
                    global_timeout=300.0,
                    cancellation_token=token,
                )
                wf_latency = (time.time() - wf_t0) * 1000

                if wf_result.status == WorkflowStatus.COMPLETED:
                    self._completed_workflows[mission_id].add(wf_id)
                    workflow_results[wf_id] = {
                        "status": "completed",
                        "node_results": {
                            nid: {"status": en.status.value, "output": en.output}
                            for nid, en in wf_result.node_results.items()
                        },
                    }
                    ctx.workflow_outputs[wf_id] = workflow_results[wf_id]
                    for nid, en in wf_result.node_results.items():
                        if en.output is not None:
                            ctx.node_outputs[f"{wf_id}.{nid}"] = en.output
                            ctx.shared_data[nid] = en.output
                    if self._monitor:
                        self._monitor.observe_latency(mission_id, wf_id, wf_latency)
                else:
                    self._failed_workflows[mission_id].add(wf_id)
                    workflow_results[wf_id] = {
                        "status": "failed",
                        "error": wf_result.error or f"Workflow '{wf_id}' failed",
                    }
                    if self._monitor:
                        self._monitor.observe_tool(
                            mission_id, wf_id, wf_id,
                            wf_latency, success=False,
                        )

                    revision_result = await self._try_revision(
                        mission_id, wf_id,
                        wf_result.error or f"Workflow '{wf_id}' failed",
                        {"tool_name": wf_id},
                    )
                    if revision_result:
                        workflow_results.update(revision_result)
                        idx += 1
                        continue

                    self._publish(MissionFailed(
                        mission_id=mission_id, name=mission.name,
                        error=wf_result.error or f"Workflow '{wf_id}' failed",
                        completed_workflows=len(self._completed_workflows[mission_id]),
                        total_workflows=len(mission.workflow_ids),
                    ))
                    break

                cp = await self._checkpoints.save(
                    mission=mission, context=ctx,
                    completed=list(self._completed_workflows[mission_id]),
                    failed=list(self._failed_workflows[mission_id]),
                    running=wf_id,
                )
                self._publish(MissionCheckpointSaved(
                    mission_id=mission_id, checkpoint_id=cp.id,
                    completed_workflows=len(self._completed_workflows[mission_id]),
                    total_workflows=len(mission.workflow_ids),
                ))

                progress = self._store.get_progress(
                    mission_id,
                    list(self._completed_workflows[mission_id]),
                    list(self._failed_workflows[mission_id]),
                )
                self._publish(MissionProgressUpdated(
                    mission_id=mission_id,
                    progress_pct=progress.progress_pct,
                    completed=progress.completed,
                    failed=progress.failed,
                    remaining=progress.remaining,
                ))

                idx += 1

                if self._scheduler and idx < len(workflow_order):
                    pending = workflow_order[idx:]
                    scheduler_ctx = {}
                    if self._monitor:
                        scheduler_ctx["latency_map"] = self._monitor.get_latency_map()
                    scheduler_ctx["priority_map"] = {
                        wf: mission.priority.value
                        for wf in pending
                    }
                    decision = await self._scheduler.reorder(
                        mission_id=mission_id,
                        pending_workflows=pending,
                        completed_workflows=self._completed_workflows.get(mission_id, set()),
                        failed_workflows=self._failed_workflows.get(mission_id, set()),
                        context=scheduler_ctx,
                    )
                    if decision.workflow_order:
                        workflow_order = (
                            workflow_order[:idx] + decision.workflow_order
                        )

        except asyncio.CancelledError:
            self._store.update_state(mission_id, MissionState.CANCELLED)
            return self._finalize(mission_id, MissionState.CANCELLED, workflow_results, ctx, t0)
        except Exception as e:
            logger.error(f"Mission {mission_id} failed with exception: {e}")
            mission = self._store.get(mission_id)
            if mission:
                self._store.update_state(mission_id, MissionState.FAILED, error=str(e))
            return self._finalize(mission_id, MissionState.FAILED, workflow_results, ctx, t0, errors=[str(e)])

        final_state = self._determine_final_state(mission_id)
        return self._finalize(mission_id, final_state, workflow_results, ctx, t0)

    def _determine_final_state(self, mission_id: str) -> MissionState:
        mission = self._store.get(mission_id)
        if mission is None:
            return MissionState.FAILED
        failed = len(self._failed_workflows.get(mission_id, set()))
        if failed > 0:
            return MissionState.FAILED
        completed = len(self._completed_workflows.get(mission_id, set()))
        if completed >= len(mission.workflow_ids):
            return MissionState.COMPLETED
        return MissionState.FAILED

    def _finalize(
        self,
        mission_id: str,
        state: MissionState,
        workflow_results: Dict[str, Any],
        ctx: MissionContext,
        t0: float,
        errors: Optional[List[str]] = None,
    ) -> MissionResult:
        mission = self._store.get(mission_id)
        if mission:
            self._store.update_state(mission_id, state)

        elapsed = (time.time() - t0) * 1000
        telemetry = self._telemetry.get(mission_id, MissionTelemetry())
        telemetry.mission_duration_ms = elapsed
        telemetry.completed_workflows = len(self._completed_workflows.get(mission_id, set()))
        telemetry.failed_workflows = len(self._failed_workflows.get(mission_id, set()))
        telemetry.remaining_workflows = 0
        if mission:
            telemetry.remaining_workflows = len(mission.workflow_ids) - telemetry.completed_workflows - telemetry.failed_workflows
        telemetry.checkpoint_count = self._checkpoints.checkpoint_count

        result = build_mission_result(
            mission or Mission(id=mission_id),
            ctx,
            workflow_results,
            telemetry,
        )
        if errors:
            result.errors = errors
            result.error = errors[0]

        self._publish_mission_completion(result)

        self._execution_count += 1
        if state in (MissionState.FAILED, MissionState.CANCELLED):
            self._failure_count += 1
        self._total_latency_ms += elapsed

        self._cleanup_mission(mission_id)
        return result

    def _publish_mission_completion(self, result: MissionResult) -> None:
        if result.status == MissionState.COMPLETED:
            self._publish(MissionCompleted(
                mission_id=result.mission_id,
                name=result.mission_name,
                total_duration_ms=result.total_duration_ms,
                completed_workflows=result.completed_workflows,
                total_workflows=result.total_workflows,
            ))
        elif result.status == MissionState.FAILED:
            self._publish(MissionFailed(
                mission_id=result.mission_id,
                name=result.mission_name,
                error=result.error or "Mission failed",
                completed_workflows=result.completed_workflows,
                total_workflows=result.total_workflows,
            ))
        elif result.status == MissionState.CANCELLED:
            self._publish(MissionCancelled(
                mission_id=result.mission_id,
                name=result.mission_name,
                reason=result.error or "Mission cancelled",
                completed_workflows=result.completed_workflows,
                total_workflows=result.total_workflows,
            ))

    async def pause_mission(self, mission_id: str) -> MissionResult:
        token = self._cancellation_tokens.get(mission_id)
        if token:
            token.cancel()

        mission = self._store.get(mission_id)
        if mission:
            self._store.update_state(mission_id, MissionState.PAUSED)

        self._telemetry[mission_id].pause_count += 1

        cp = self._checkpoints.get_latest_checkpoint(mission_id)
        if cp:
            return MissionResult(
                mission_id=mission_id,
                status=MissionState.PAUSED,
                total_workflows=len(mission.workflow_ids) if mission else 0,
                completed_workflows=len(cp.completed_workflows),
                telemetry=self._telemetry.get(mission_id, MissionTelemetry()),
            )
        return MissionResult(
            mission_id=mission_id,
            status=MissionState.PAUSED,
            total_workflows=len(mission.workflow_ids) if mission else 0,
        )

    async def resume_mission(self, mission_id: str) -> MissionResult:
        mission = self._store.get(mission_id)
        if mission is None:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' not found",
                errors=[f"Mission '{mission_id}' not found"],
            )
        if mission.state != MissionState.PAUSED:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' is not paused (state: {mission.state.value})",
                errors=[f"Mission '{mission_id}' is not paused"],
            )

        cp = self._checkpoints.get_latest_checkpoint(mission_id)
        if cp:
            ctx = await self._checkpoints.recover(mission, cp)
            self._mission_contexts[mission_id] = ctx

        if mission_id not in self._completed_workflows:
            self._completed_workflows[mission_id] = set()
        if mission_id not in self._failed_workflows:
            self._failed_workflows[mission_id] = set()
        if cp:
            self._completed_workflows[mission_id] = set(cp.completed_workflows)
            self._failed_workflows[mission_id] = set(cp.failed_workflows)

        self._telemetry[mission_id].resume_count += 1

        return await self._execute_mission(mission_id)

    async def cancel_mission(self, mission_id: str, reason: str = "User requested cancellation") -> MissionResult:
        token = self._cancellation_tokens.get(mission_id)
        if token:
            token.cancel()

        task = self._running_tasks.get(mission_id)
        if task and not task.done():
            task.cancel()

        mission = self._store.get(mission_id)
        if mission:
            self._store.update_state(mission_id, MissionState.CANCELLED)

        self._telemetry[mission_id].cancel_count += 1
        self._publish(MissionCancelled(
            mission_id=mission_id,
            name=mission.name if mission else "",
            reason=reason,
            completed_workflows=len(self._completed_workflows.get(mission_id, set())),
            total_workflows=len(mission.workflow_ids) if mission else 0,
        ))

        return MissionResult(
            mission_id=mission_id,
            mission_name=mission.name if mission else "",
            status=MissionState.CANCELLED,
            total_workflows=len(mission.workflow_ids) if mission else 0,
            completed_workflows=len(self._completed_workflows.get(mission_id, set())),
            telemetry=self._telemetry.get(mission_id, MissionTelemetry()),
        )

    async def retry_failed_workflow(self, mission_id: str, workflow_id: str) -> MissionResult:
        mission = self._store.get(mission_id)
        if mission is None:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Mission '{mission_id}' not found",
            )
        if workflow_id not in self._failed_workflows.get(mission_id, set()):
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Workflow '{workflow_id}' not found in failed workflows",
            )

        self._failed_workflows[mission_id].discard(workflow_id)
        self._store.update_state(mission_id, MissionState.RUNNING)

        token = CancellationToken()
        self._cancellation_tokens[mission_id] = token
        ctx = self._mission_contexts.get(mission_id) or MissionContext(mission_id=mission_id)
        t0 = time.time()

        graph = self._workflow_graphs.get(workflow_id)
        if graph is None:
            return MissionResult(
                mission_id=mission_id, status=MissionState.FAILED,
                error=f"Workflow graph '{workflow_id}' not registered",
            )

        wf_result = await self._workflow_executor.execute(
            graph=graph,
            global_timeout=300.0,
            cancellation_token=token,
        )

        workflow_results: Dict[str, Any] = {}
        if wf_result.status == WorkflowStatus.COMPLETED:
            self._completed_workflows[mission_id].add(workflow_id)
            workflow_results[workflow_id] = {"status": "completed"}
        else:
            self._failed_workflows[mission_id].add(workflow_id)
            workflow_results[workflow_id] = {"status": "failed", "error": wf_result.error}

        remaining = [wf for wf in mission.workflow_ids
                     if wf not in self._completed_workflows[mission_id]
                     and wf not in self._failed_workflows[mission_id]]
        if remaining:
            return await self._execute_mission(mission_id)

        final_state = self._determine_final_state(mission_id)
        return self._finalize(mission_id, final_state, workflow_results, ctx, t0)

    def _cleanup_mission(self, mission_id: str) -> None:
        self._running_tasks.pop(mission_id, None)
        self._cancellation_tokens.pop(mission_id, None)

    def is_running(self, mission_id: str) -> bool:
        return mission_id in self._running_tasks and not self._running_tasks[mission_id].done()

    def list_missions(self) -> List[Mission]:
        return self._store.list_missions()

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self._store.get(mission_id)

    def get_progress(self, mission_id: str) -> MissionProgress:
        return self._store.get_progress(
            mission_id,
            list(self._completed_workflows.get(mission_id, set())),
            list(self._failed_workflows.get(mission_id, set())),
        )

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass

    def health(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": "HEALTHY",
            "execution_count": self._execution_count,
            "failure_count": self._failure_count,
            "active_missions": len(self._running_tasks),
            "total_missions": self._store.count,
            "average_latency_ms": round(
                self._total_latency_ms / max(self._execution_count, 1), 2
            ),
            "revision_count": self._revision_count,
        }
        if self._scheduler:
            result["scheduler_stats"] = self._scheduler.get_stats()
        if self._monitor:
            result["monitor_stats"] = self._monitor.get_stats()
        return result
