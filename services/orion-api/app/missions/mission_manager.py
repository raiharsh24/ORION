import uuid
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from loguru import logger

from app.missions.mission import Mission, MissionStatus, MissionPriority, MissionType
from app.events.events import OrionEvent

# Telemetry Interface & Class
class MissionTelemetry:
    """
    Interface/class for recording mission execution metrics.
    """
    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def record(
        self,
        mission_id: str,
        status: str,
        duration: float,
        started_at: datetime,
        finished_at: datetime,
        error: Optional[str] = None
    ) -> None:
        """
        Saves a telemetry entry for a mission execution run.
        """
        entry = {
            "mission_id": mission_id,
            "status": status,
            "duration": duration,
            "started_at": started_at,
            "finished_at": finished_at,
            "error": error
        }
        self.records.append(entry)
        logger.info(
            f"Telemetry Recorded: ID={mission_id} | Status={status} | "
            f"Duration={duration:.2f}s | Error={error}"
        )


# API Contracts (Request/Response Models)
class CreateMissionRequest(BaseModel):
    name: str = Field(..., description="Name of the mission")
    description: str = Field(..., description="Details and goal of the mission")
    priority: str = Field("NORMAL", description="LOW, NORMAL, HIGH, CRITICAL")
    type: str = Field("USER_DEFINED", description="DEVELOPMENT, AUTOMATION, KNOWLEDGE, SYSTEM, USER_DEFINED")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata key-value pairs")

class MissionResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    priority: str
    type: str
    workflow_id: Optional[str] = None
    progress: float
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

class MissionProgress(BaseModel):
    mission_id: str
    status: str
    current_step: Optional[str] = None
    progress: float
    updated_at: datetime

class MissionSummary(BaseModel):
    total_missions: int
    active_missions: int
    completed_missions: int
    failed_missions: int
    recent_missions: List[MissionResponse]


# Built-in Mission Definitions (Metadata / Blueprints only)
BUILTIN_MISSIONS = {
    "dev_startup": {
        "name": "Development Startup",
        "description": "Initialize local development services, database containers, and frontend servers.",
        "type": MissionType.DEVELOPMENT,
        "priority": MissionPriority.HIGH,
        "metadata": {"category": "devops", "auto_run": False}
    },
    "dev_shutdown": {
        "name": "Development Shutdown",
        "description": "Gracefully terminate dev servers, clear temp logs, and close docker containers.",
        "type": MissionType.DEVELOPMENT,
        "priority": MissionPriority.NORMAL,
        "metadata": {"category": "devops"}
    },
    "run_tests": {
        "name": "Run Tests",
        "description": "Execute system test suite under tests/ directory and output coverage metrics.",
        "type": MissionType.DEVELOPMENT,
        "priority": MissionPriority.HIGH,
        "metadata": {"category": "quality"}
    },
    "build_project": {
        "name": "Build Project",
        "description": "Compile TypeScript/Vite assets and package production api binaries.",
        "type": MissionType.DEVELOPMENT,
        "priority": MissionPriority.CRITICAL,
        "metadata": {"category": "release"}
    },
    "repository_index": {
        "name": "Repository Index",
        "description": "Scan workspace directories and index files to ChromaDB vector store.",
        "type": MissionType.KNOWLEDGE,
        "priority": MissionPriority.NORMAL,
        "metadata": {"category": "search"}
    },
    "health_check": {
        "name": "Health Check",
        "description": "Probe API endpoints, system memory, CPU cycles, and network status indicators.",
        "type": MissionType.SYSTEM,
        "priority": MissionPriority.NORMAL,
        "metadata": {"category": "maintenance"}
    },
    "workspace_cleanup": {
        "name": "Workspace Cleanup",
        "description": "Clear generated logs, caches, and dangling temporary files from storage directories.",
        "type": MissionType.SYSTEM,
        "priority": MissionPriority.LOW,
        "metadata": {"category": "maintenance"}
    },
    "desktop_demo": {
        "name": "Desktop Demo Automation",
        "description": "Execute sequential desktop tasks (open notification, open folder, write clipboard).",
        "type": MissionType.AUTOMATION,
        "priority": MissionPriority.NORMAL,
        "metadata": {
            "category": "automation",
            "actions": [
                {"action": "show_notification", "message": "Starting desktop automation demo", "title": "ORION"},
                {"action": "open_folder", "folder_path": "/home/warlock"},
                {"action": "write_clipboard", "text": "ORION OS Clipboard content"},
                {"action": "read_clipboard"},
                {"action": "open_url", "url": "https://google.com"},
                {"action": "open_application", "app_name": "xterm"},
                {"action": "close_application", "app_name": "xterm"}
            ]
        }
    }
}


# Valid state transitions
ALLOWED_TRANSITIONS = {
    MissionStatus.CREATED: {MissionStatus.QUEUED, MissionStatus.CANCELLED},
    MissionStatus.QUEUED: {MissionStatus.RUNNING, MissionStatus.CANCELLED},
    MissionStatus.RUNNING: {MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.PAUSED: {MissionStatus.RUNNING, MissionStatus.CANCELLED, MissionStatus.FAILED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.FAILED: set(),
    MissionStatus.CANCELLED: set()
}


class MissionManager:
    """
    Coordinates user goals and schedules workflows to fulfill missions.
    
    Integrations:
    - **Planner**: Compiles the high-level mission goal into sequential steps.
    - **WorkflowEngine**: Executes, monitors, and coordinates workflow steps.
    - **Scheduler**: Schedules recurring or delayed missions.
    - **DesktopController**: Invokes automation tools directly when necessary.
    - **Knowledge Engine**: Retrieves context data and local project details.
    - **Tool Registry**: Inspects and executes individual tools requested by steps.
    - **Event Bus**: Publishes mission state transitions.
    - **Telemetry**: Writes diagnostic records and execution time statistics.
    - **Safety Policies**: Validates whether actions in a mission adhere to restrictions.
    """
    def __init__(
        self,
        planner: Optional[Any] = None,
        workflow_engine: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        desktop_controller: Optional[Any] = None,
        knowledge_engine: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        telemetry: Optional[MissionTelemetry] = None,
        safety_policies: Optional[Any] = None,
        history: Optional[Any] = None
    ) -> None:
        """
        Initialize the MissionManager using Dependency Injection.
        """
        self._planner = planner
        self._workflow_engine = workflow_engine
        self._scheduler = scheduler
        self._desktop_controller = desktop_controller
        self._knowledge_engine = knowledge_engine
        self._tool_registry = tool_registry
        self._event_bus = event_bus
        self._telemetry = telemetry or MissionTelemetry()
        self._safety_policies = safety_policies
        self._history = history

        self._active_missions: Dict[str, Mission] = {}
        self._start_times: Dict[str, datetime] = {}
        
        # Load registry built-in blueprints
        self._registry: Dict[str, Dict[str, Any]] = BUILTIN_MISSIONS.copy()

    def _validate_transition(self, current: MissionStatus, target: MissionStatus) -> None:
        if current == target:
            return  # No-op
        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ValueError(f"Invalid state transition from {current.value} to {target.value}")

    def _to_response(self, mission: Mission) -> MissionResponse:
        return MissionResponse(
            id=mission.id,
            name=mission.name,
            description=mission.description,
            status=mission.status.value,
            priority=mission.priority.value,
            type=mission.type.value,
            workflow_id=mission.workflow_id,
            progress=mission.progress,
            created_at=mission.created_at,
            updated_at=mission.updated_at,
            metadata=mission.metadata
        )

    async def create_mission(self, request: CreateMissionRequest) -> MissionResponse:
        """
        Creates a new mission instance and registers it.
        """
        mission_id = uuid.uuid4().hex
        
        # Resolve priority & type enums
        try:
            priority = MissionPriority(request.priority.upper())
        except ValueError:
            priority = MissionPriority.NORMAL

        try:
            m_type = MissionType(request.type.upper())
        except ValueError:
            m_type = MissionType.USER_DEFINED

        mission = Mission(
            id=mission_id,
            name=request.name,
            description=request.description,
            priority=priority,
            type=m_type,
            metadata=request.metadata,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self._active_missions[mission_id] = mission
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionCreated", {"mission_id": mission_id, "name": mission.name})
            )

        return self._to_response(mission)

    async def queue_mission(self, mission_id: str) -> bool:
        """
        Transitions a mission to QUEUED status.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.QUEUED)
        
        mission.status = MissionStatus.QUEUED
        mission.updated_at = datetime.now(timezone.utc)
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionQueued", {"mission_id": mission_id})
            )

        return True

    async def start_mission(self, mission_id: str) -> bool:
        """
        Launches execution for a queued mission.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.RUNNING)
        
        mission.status = MissionStatus.RUNNING
        mission.updated_at = datetime.now(timezone.utc)
        self._start_times[mission_id] = datetime.now(timezone.utc)
        
        if mission.type == MissionType.AUTOMATION:
            from app.kernel.kernel import OrionKernel
            desktop_automation = OrionKernel.get_instance().get_service("desktop_automation")
            if desktop_automation:
                desktop_automation.add_mission(mission_id)
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionStarted", {"mission_id": mission_id})
            )

        return True

    async def pause_mission(self, mission_id: str) -> bool:
        """
        Pauses a running mission workflow.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.PAUSED)
        
        mission.status = MissionStatus.PAUSED
        mission.updated_at = datetime.now(timezone.utc)
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionPaused", {"mission_id": mission_id})
            )

        return True

    async def resume_mission(self, mission_id: str) -> bool:
        """
        Resumes a paused mission.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.RUNNING)
        
        mission.status = MissionStatus.RUNNING
        mission.updated_at = datetime.now(timezone.utc)
        
        if mission.type == MissionType.AUTOMATION:
            from app.kernel.kernel import OrionKernel
            desktop_automation = OrionKernel.get_instance().get_service("desktop_automation")
            if desktop_automation:
                desktop_automation.add_mission(mission_id)
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionStarted", {"mission_id": mission_id})
            )

        return True

    async def cancel_mission(self, mission_id: str) -> bool:
        """
        Cancels a mission.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.CANCELLED)
        
        mission.status = MissionStatus.CANCELLED
        mission.updated_at = datetime.now(timezone.utc)
        
        if mission.type == MissionType.AUTOMATION:
            from app.kernel.kernel import OrionKernel
            desktop_automation = OrionKernel.get_instance().get_service("desktop_automation")
            if desktop_automation:
                desktop_automation.cancel_mission(mission_id)
        
        finished_at = datetime.now(timezone.utc)
        started_at = self._start_times.get(mission_id, finished_at)
        duration = (finished_at - started_at).total_seconds()
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionCancelled", {"mission_id": mission_id})
            )

        if self._telemetry:
            self._telemetry.record(
                mission_id=mission_id,
                status=MissionStatus.CANCELLED.value,
                duration=duration,
                started_at=started_at,
                finished_at=finished_at,
                error="Cancelled by user"
            )

        return True

    async def complete_mission(self, mission_id: str) -> bool:
        """
        Completes the mission.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.COMPLETED)
        
        mission.status = MissionStatus.COMPLETED
        mission.progress = 1.0
        mission.updated_at = datetime.now(timezone.utc)
        
        finished_at = datetime.now(timezone.utc)
        started_at = self._start_times.get(mission_id, finished_at)
        duration = (finished_at - started_at).total_seconds()
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionCompleted", {"mission_id": mission_id})
            )

        if self._telemetry:
            self._telemetry.record(
                mission_id=mission_id,
                status=MissionStatus.COMPLETED.value,
                duration=duration,
                started_at=started_at,
                finished_at=finished_at
            )

        return True

    async def fail_mission(self, mission_id: str, error_message: str) -> bool:
        """
        Fails the mission.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return False

        self._validate_transition(mission.status, MissionStatus.FAILED)
        
        mission.status = MissionStatus.FAILED
        mission.updated_at = datetime.now(timezone.utc)
        mission.metadata["error"] = error_message
        
        finished_at = datetime.now(timezone.utc)
        started_at = self._start_times.get(mission_id, finished_at)
        duration = (finished_at - started_at).total_seconds()
        
        if self._history:
            await self._history.save(mission)

        if self._event_bus:
            await self._event_bus.publish(
                OrionEvent("MissionFailed", {"mission_id": mission_id, "error": error_message})
            )

        if self._telemetry:
            self._telemetry.record(
                mission_id=mission_id,
                status=MissionStatus.FAILED.value,
                duration=duration,
                started_at=started_at,
                finished_at=finished_at,
                error=error_message
            )

        return True

    async def list_missions(self, type_filter: Optional[MissionType] = None) -> List[MissionResponse]:
        """
        Lists actively registered missions.
        """
        missions = list(self._active_missions.values())
        if type_filter:
            missions = [m for m in missions if m.type == type_filter]
        return [self._to_response(m) for m in missions]

    async def get_mission(self, mission_id: str) -> Optional[MissionResponse]:
        """
        Gets a mission by ID.
        """
        mission = self._active_missions.get(mission_id)
        if not mission:
            return None
        return self._to_response(mission)

    def get_registered_builtins(self) -> Dict[str, Dict[str, Any]]:
        """
        Exposes registered built-in metadata blueprints.
        """
        return self._registry
