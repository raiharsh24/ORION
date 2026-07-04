from typing import Any, Optional, List, Dict
from datetime import datetime, timezone

from app.runtime.base import Mission, ExecutionResult
from app.runtime.orchestrator import Orchestrator
from app.runtime.queue import MissionQueue, MissionPriority, QueueStatus
from app.runtime.persistence import MissionStore
from app.runtime.health import RuntimeHealth
from app.runtime.telemetry import MissionTelemetry


class MissionRuntime:
    def __init__(self, agent_manager: Any = None,
                 planning_engine: Any = None,
                 workflow_engine: Any = None,
                 tool_execution_engine: Any = None,
                 tool_selection_engine: Any = None,
                 capability_resolver: Any = None,
                 capability_registry: Any = None,
                 plugin_runtime: Any = None,
                 memory_engine: Any = None,
                 plan_memory: Any = None,
                 max_concurrent: int = 4):
        self._orchestrator = Orchestrator(
            agent_manager=agent_manager,
            planning_engine=planning_engine,
            workflow_engine=workflow_engine,
            tool_execution_engine=tool_execution_engine,
            tool_selection_engine=tool_selection_engine,
            capability_resolver=capability_resolver,
            capability_registry=capability_registry,
            plugin_runtime=plugin_runtime,
            memory_engine=memory_engine,
        )
        self._queue = MissionQueue(max_concurrent=max_concurrent)
        self._store = MissionStore()
        self._started_at = datetime.now(timezone.utc)

        self._queue.set_handler(self._queue_handler)
        self._queue.on_completion(self._queue_completion_hook)

    def set_event_bus(self, event_bus: Any) -> None:
        self._orchestrator.set_event_bus(event_bus)

    async def _queue_handler(self, mission_id: str) -> ExecutionResult:
        mission = self._orchestrator.get_mission(mission_id)
        if not mission:
            record = self._store.load_mission(mission_id)
            if record:
                mission = Mission(
                    mission_id=record.mission_id,
                    user_request=record.user_request,
                    intent=record.intent,
                    status=record.status,
                    metadata=record.metadata,
                )
                self._orchestrator._missions[mission_id] = mission
            else:
                raise ValueError(f"Mission {mission_id} not found")
        result = await self._orchestrator.run_lifecycle(mission)
        return result

    def _queue_completion_hook(self, mission_id: str,
                                result: Any, error: Optional[str]) -> None:
        pass

    async def submit(self, user_request: str, intent: str = "",
                     metadata: Optional[Dict[str, Any]] = None,
                     priority: int = MissionPriority.MEDIUM,
                     dependency_ids: Optional[List[str]] = None,
                     timeout_s: float = 300.0) -> Mission:
        mission = await self._orchestrator.submit_request(
            user_request, intent, metadata,
        )
        await self._queue.enqueue(
            mission.mission_id,
            priority=priority,
            dependency_ids=dependency_ids,
            timeout_s=timeout_s,
        )
        self._queue.start_processing()
        return mission

    async def run(self, mission: Mission) -> ExecutionResult:
        return await self._orchestrator.run_lifecycle(mission)

    async def submit_and_run(self, user_request: str, intent: str = "",
                              metadata: Optional[Dict[str, Any]] = None,
                              priority: int = MissionPriority.MEDIUM,
                              timeout_s: float = 300.0) -> ExecutionResult:
        mission = await self.submit(user_request, intent, metadata,
                                     priority=priority, timeout_s=timeout_s)
        await self._queue.wait_for_all()
        record = self._store.load_mission(mission.mission_id)
        if record:
            return ExecutionResult(
                success=record.status == "completed",
                mission_id=mission.mission_id,
                error=record.error,
            )
        return ExecutionResult(
            success=False,
            mission_id=mission.mission_id,
            error="Mission not found after execution",
        )

    async def submit_background(self, user_request: str, intent: str = "",
                                 metadata: Optional[Dict[str, Any]] = None,
                                 priority: int = MissionPriority.MEDIUM,
                                 dependency_ids: Optional[List[str]] = None,
                                 timeout_s: float = 300.0) -> str:
        mission = await self.submit(user_request, intent, metadata,
                                     priority=priority,
                                     dependency_ids=dependency_ids,
                                     timeout_s=timeout_s)
        return mission.mission_id

    async def pause(self, mission_id: str) -> bool:
        return await self._orchestrator.pause_mission(mission_id)

    async def resume(self, mission_id: str) -> bool:
        return await self._orchestrator.resume_mission(mission_id)

    async def cancel(self, mission_id: str) -> bool:
        queued_cancelled = await self._queue.cancel(mission_id)
        orch_cancelled = await self._orchestrator.cancel_mission(mission_id)
        return queued_cancelled or orch_cancelled

    async def retry(self, mission_id: str) -> bool:
        return await self._queue.retry(mission_id)

    async def archive(self, mission_id: str) -> bool:
        return await self._orchestrator.archive_mission(mission_id)

    async def shutdown(self) -> None:
        """Cancel all missions, drain queue, and reset state."""
        from loguru import logger
        logger.info("Shutting down MissionRuntime...")
        for mission in self._orchestrator.list_missions():
            if mission.status in ("created", "planning", "ready", "running", "recovering"):
                await self.cancel(mission.mission_id)
        self._queue.stop_processing()
        self._orchestrator._missions.clear()
        self._orchestrator.telemetry.reset()
        self._orchestrator.metrics.reset()
        self._store = MissionStore()
        logger.info("MissionRuntime shutdown complete")

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        return self._orchestrator.get_mission(mission_id)

    def _mission_in_queue_set(self, mission_id: str,
                               s: set) -> bool:
        return mission_id in s

    def get_status(self, mission_id: str) -> Optional[str]:
        mission = self._orchestrator.get_mission(mission_id)
        if mission:
            return mission.status
        if self._queue.is_running(mission_id):
            return "running"
        if self._queue.is_completed(mission_id):
            return "completed"
        if self._queue.is_failed(mission_id):
            return "failed"
        if self._queue.is_cancelled(mission_id):
            return "cancelled"
        if mission_id in self._queue.list_queued():
            return "queued"
        record = self._store.load_mission(mission_id)
        if record:
            return record.status
        return None

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        for mission in self._orchestrator.list_missions():
            history.append({
                "mission_id": mission.mission_id,
                "user_request": mission.user_request,
                "intent": mission.intent,
                "status": mission.status,
                "created_at": str(mission.created_at),
                "completed_at": str(mission.completed_at) if mission.completed_at else None,
                "duration_ms": mission.total_duration_ms,
                "error": mission.error,
                "stages": [{"name": s.name, "status": s.status,
                            "error": s.error}
                           for s in mission.stages],
            })
        stored_ids = self._store.list_missions()
        known_ids = {m.mission_id for m in self._orchestrator.list_missions()}
        for mid in stored_ids:
            if mid not in known_ids:
                record = self._store.load_mission(mid)
                if record:
                    history.append({
                        "mission_id": record.mission_id,
                        "user_request": record.user_request,
                        "intent": record.intent,
                        "status": record.status,
                        "created_at": record.created_at,
                        "completed_at": record.completed_at,
                        "duration_ms": 0.0,
                        "error": record.error,
                        "stages": [
                            {"name": n, "status": record.stage_statuses.get(n, "unknown"),
                             "error": record.stage_errors.get(n, None)}
                            for n in record.stage_names
                        ],
                    })
        history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return history[:limit]

    def list_missions(self) -> List[Mission]:
        return self._orchestrator.list_missions()

    def queue_status(self) -> QueueStatus:
        return self._queue.status

    def metrics(self) -> Any:
        return self._orchestrator.metrics.snapshot()

    def telemetry_summary(self) -> Dict[str, Any]:
        return self._orchestrator.telemetry.snapshot()

    def get_telemetry(self, mission_id: str) -> Optional[MissionTelemetry]:
        return self._orchestrator.telemetry.get_mission(mission_id)

    def health(self) -> RuntimeHealth:
        h = self._orchestrator.health()
        qs = self._queue.status
        uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds() / 3600
        return RuntimeHealth(
            status=h.get("status", "healthy"),
            running_missions=h.get("running_missions", 0),
            completed_missions=h.get("completed_missions", 0),
            failed_missions=h.get("failed_missions", 0),
            queued_missions=qs.queued,
            paused_missions=h.get("paused_missions", 0),
            average_runtime_ms=h.get("average_runtime_ms", 0.0),
            total_retries=h.get("total_retries", 0),
            total_recoveries=h.get("total_recoveries", 0),
            recovery_success_rate=h.get("recovery_success_rate", 1.0),
            uptime_hours=round(uptime, 2),
            max_concurrent=self._queue._max_concurrent,
            success_rate=h.get("success_rate", 1.0),
            dispatcher_available=h.get("dispatcher_available", True),
            executor_available=h.get("executor_available", True),
            supervisor_available=h.get("supervisor_available", True),
        )
