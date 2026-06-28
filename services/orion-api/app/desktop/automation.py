import asyncio
import os
import sys
import subprocess
import webbrowser
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger

from app.capabilities.capability import BaseCapability
from app.missions.mission import MissionStatus
from app.events.events import OrionEvent

class DesktopAutomationService(BaseCapability):
    """
    Central service for orchestrating safe, queue-based desktop automation tasks.
    Coordinates sequential action dispatching, user confirmation gates, and diagnostics telemetry.
    """
    def __init__(self) -> None:
        self._queue: List[str] = []
        self._is_paused: bool = False
        self._confirmations: Dict[str, asyncio.Future] = {}
        
        # Telemetry / Developer Diagnostics
        self._current_task_id: Optional[str] = None
        self._current_action: Optional[str] = None
        self._last_executed_action: Optional[str] = None
        self._total_execution_time: float = 0.0
        self._total_executed_actions: int = 0
        self._failure_count: int = 0
        
        self._loop_task: Optional[asyncio.Task] = None

    @property
    def name(self) -> str:
        return "desktop_automation"

    @property
    def schema(self) -> Dict[str, Any]:
        return {}

    async def initialize(self) -> None:
        """Starts the background execution queue worker loop."""
        self._loop_task = asyncio.create_task(self._queue_worker())

    async def validate(self, **kwargs) -> bool:
        return True

    async def execute(self, **kwargs) -> Any:
        pass

    async def rollback(self) -> bool:
        return True

    async def shutdown(self) -> None:
        """Gracefully terminates background execution queue loops."""
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    # Queue Management
    def add_mission(self, mission_id: str) -> None:
        if mission_id not in self._queue:
            self._queue.append(mission_id)

    def pause_queue(self) -> None:
        self._is_paused = True

    def resume_queue(self) -> None:
        self._is_paused = False

    def cancel_mission(self, mission_id: str) -> None:
        if mission_id in self._queue:
            self._queue.remove(mission_id)
        if self._current_task_id == mission_id:
            # Cancel any pending confirmation future
            fut = self._confirmations.pop(mission_id, None)
            if fut and not fut.done():
                fut.set_result(False)

    def confirm_action(self, mission_id: str, approved: bool) -> bool:
        fut = self._confirmations.pop(mission_id, None)
        if fut and not fut.done():
            fut.set_result(approved)
            return True
        return False

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY" if not self._is_paused else "WARNING",
            "message": "Automation queue active." if not self._is_paused else "Queue paused.",
            "details": self.get_diagnostics()
        }

    # Diagnostics Mappings
    def get_diagnostics(self) -> Dict[str, Any]:
        avg_time = 0.0
        if self._total_executed_actions > 0:
            avg_time = round((self._total_execution_time / self._total_executed_actions) * 1000, 1)
            
        return {
            "current_desktop_task": self._current_task_id or "None",
            "last_executed_action": self._last_executed_action or "None",
            "average_execution_time_ms": avg_time,
            "failure_count": self._failure_count,
            "queue_length": len(self._queue),
            "is_paused": self._is_paused,
            "active_action": self._current_action or "None"
        }

    async def _queue_worker(self) -> None:
        """Processes sequential desktop actions in a safe FIFO queue."""
        while True:
            try:
                if self._is_paused or not self._queue:
                    await asyncio.sleep(0.5)
                    continue

                mission_id = self._queue[0]
                self._current_task_id = mission_id

                from app.kernel.kernel import OrionKernel
                kernel = OrionKernel.get_instance()
                manager = kernel.get_service("mission_engine")
                if not manager:
                    await asyncio.sleep(0.5)
                    continue

                mission = manager._active_missions.get(mission_id)
                if not mission or mission.status != MissionStatus.RUNNING:
                    # Remove terminated/paused mission from queue front
                    self._queue.pop(0)
                    self._current_task_id = None
                    continue

                # Retrieve automation steps list
                actions = mission.metadata.get("actions", [])
                if not actions:
                    # Demo fallback if actions array isn't populated
                    actions = [
                        {"action": "show_notification", "message": "Executing setup", "title": "ORION"},
                        {"action": "write_clipboard", "text": "ORION Test"},
                        {"action": "read_clipboard"}
                    ]
                    mission.metadata["actions"] = actions

                total = len(actions)
                completed = mission.metadata.get("completed_actions", 0)
                
                # Setup steps representation for timeline
                mission.metadata["steps"] = [a.get("action", "Action") for a in actions]

                success = True
                for idx in range(completed, total):
                    # Check connection and queue state transitions
                    if mission.status == MissionStatus.PAUSED or self._is_paused:
                        break
                    if mission.status == MissionStatus.CANCELLED:
                        success = False
                        break

                    action_data = actions[idx]
                    action_name = action_data.get("action")
                    
                    self._current_action = action_name
                    mission.current_step = action_name
                    
                    logs = mission.metadata.setdefault("logs", [])
                    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    logs.append({
                        "time": timestamp,
                        "level": "INFO",
                        "msg": f"Executing: {action_name}"
                    })

                    event_bus = kernel.get_service("event_bus")
                    if event_bus:
                        payload = _map_to_detailed_dict(mission, manager)
                        await event_bus.publish(OrionEvent("MissionUpdated", payload))

                    # Sensitive Gate Checks
                    is_sensitive = action_name in ["open_application", "close_application", "write_clipboard"]
                    if is_sensitive:
                        # Enter human-in-the-loop pending approval state
                        mission.metadata["pending_confirmation"] = {
                            "action": action_name,
                            "args": {k: v for k, v in action_data.items() if k != "action"},
                            "prompt": f"Confirm Sensitive Desktop Request: {action_name.replace('_', ' ').title()}"
                        }
                        logs.append({
                            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                            "level": "WARN",
                            "msg": f"Pending authorization for sensitive action: {action_name}"
                        })
                        
                        if event_bus:
                            payload = _map_to_detailed_dict(mission, manager)
                            await event_bus.publish(OrionEvent("MissionUpdated", payload))

                        # Block on confirm future
                        fut = asyncio.Future()
                        self._confirmations[mission_id] = fut
                        approved = await fut

                        self._confirmations.pop(mission_id, None)
                        mission.metadata.pop("pending_confirmation", None)

                        if not approved:
                            success = False
                            logs.append({
                                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                                "level": "ERROR",
                                "msg": f"Authorization rejected by user."
                            })
                            await manager.fail_mission(mission_id, f"User rejected sensitive action: {action_name}")
                            break
                        else:
                            logs.append({
                                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                                "level": "INFO",
                                "msg": f"Action authorized."
                            })

                    # Execute Action
                    start_time = datetime.now(timezone.utc)
                    action_success = False
                    action_error = None
                    try:
                        action_success = await self._run_action(action_name, action_data)
                    except Exception as e:
                        action_error = str(e)

                    end_time = datetime.now(timezone.utc)
                    dur = (end_time - start_time).total_seconds()
                    
                    self._last_executed_action = action_name
                    self._total_execution_time += dur
                    self._total_executed_actions += 1

                    if action_success:
                        logs.append({
                            "time": end_time.strftime("%H:%M:%S"),
                            "level": "SUCCESS",
                            "msg": f"Completed: {action_name} in {dur:.2f}s"
                        })
                        mission.metadata["completed_actions"] = idx + 1
                        mission.progress = min(100.0, round(((idx + 1) / total) * 100.0, 1))
                    else:
                        self._failure_count += 1
                        err_msg = action_error or "Execution failed."
                        logs.append({
                            "time": end_time.strftime("%H:%M:%S"),
                            "level": "ERROR",
                            "msg": f"Action failed: {err_msg}"
                        })
                        success = False
                        await manager.fail_mission(mission_id, f"Action {action_name} failed: {err_msg}")
                        break

                    await asyncio.sleep(0.8) # Micro delay between ticks for visual tracing

                if success:
                    # Dequeue completed item
                    if self._queue and self._queue[0] == mission_id:
                        self._queue.pop(0)
                    self._current_task_id = None
                    self._current_action = None
                    await manager.complete_mission(mission_id)
                else:
                    if self._queue and self._queue[0] == mission_id:
                        self._queue.pop(0)
                    self._current_task_id = None
                    self._current_action = None

            except Exception as e:
                logger.error(f"Error in DesktopAutomationService queue loop: {str(e)}")
                await asyncio.sleep(1.0)

    async def _run_action(self, name: str, params: Dict[str, Any]) -> bool:
        """Invokes capability modules matching requested actions."""
        from app.kernel.kernel import OrionKernel
        kernel = OrionKernel.get_instance()
        desktop = kernel.get_service("desktop_controller")
        if not desktop:
            raise RuntimeError("DesktopController service not registered.")

        if name == "open_application":
            res = await desktop.open_application(params.get("app_name", ""), params.get("args"))
            return res.get("success", False)
            
        elif name == "close_application":
            res = await desktop.close_application(params.get("app_name", ""))
            return res.get("success", False)
            
        elif name == "list_running_processes":
            res = await desktop.list_running_processes()
            return isinstance(res, list)
            
        elif name == "take_screenshot":
            res = await desktop.take_screenshot(params.get("save_path"))
            return len(res) >= 0
            
        elif name == "read_clipboard":
            await desktop.read_clipboard()
            return True
            
        elif name == "write_clipboard":
            res = await desktop.copy_to_clipboard(params.get("text", ""))
            return bool(res)
            
        elif name == "show_notification":
            res = await desktop.show_notification(params.get("message", ""), params.get("title"))
            return bool(res)
            
        elif name == "open_folder":
            folder_path = params.get("folder_path")
            if not folder_path:
                raise ValueError("folder_path parameter is missing.")
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
            return True
            
        elif name == "open_url":
            url = params.get("url")
            if not url:
                raise ValueError("url parameter is missing.")
            webbrowser.open(url)
            return True
            
        else:
            raise ValueError(f"Unknown desktop automation action keyword: {name}")

def _map_to_detailed_dict(mission, manager) -> Dict[str, Any]:
    """Decoupled mapper preventing circular imports with FastAPI models."""
    start_time = manager._start_times.get(mission.id)
    duration_ms = 0
    if start_time:
        end_time = datetime.now(timezone.utc) if mission.status.value == "RUNNING" else mission.updated_at
        duration_ms = int((end_time.replace(tzinfo=timezone.utc) - start_time.replace(tzinfo=timezone.utc)).total_seconds() * 1000)

    steps = mission.metadata.get("steps", ["Init", "Process Tasks", "Verify Output", "Done"])
    workflow_name = mission.metadata.get("workflowName") or "desktop_automation"
    current_tool = mission.metadata.get("current_tool") if mission.status.value == "RUNNING" else None
    logs_data = mission.metadata.get("logs") or []

    return {
        "id": mission.id,
        "name": mission.name,
        "description": mission.description,
        "status": mission.status.value,
        "priority": mission.priority.value,
        "type": mission.type.value,
        "workflow_id": mission.workflow_id,
        "progress": mission.progress,
        "created_at": mission.created_at.isoformat(),
        "updated_at": mission.updated_at.isoformat(),
        "metadata": mission.metadata,
        "currentStep": mission.current_step or "Pending Queue",
        "steps": steps,
        "durationMs": max(0, duration_ms),
        "startedAt": start_time.strftime("%H:%M:%S") if start_time else None,
        "finishedAt": mission.updated_at.strftime("%H:%M:%S") if mission.status.value in ["COMPLETED", "FAILED", "CANCELLED"] else None,
        "error": mission.metadata.get("error"),
        "currentTool": current_tool,
        "workflowName": workflow_name,
        "logs": logs_data
    }
