import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from app.mission_engine.base import (
    Mission, MissionState, MissionPriority, MissionProgress,
)


class MissionStore:
    def __init__(self) -> None:
        self._missions: Dict[str, Mission] = {}

    def create(self, name: str = "", description: str = "",
               workflow_ids: Optional[List[str]] = None,
               priority: MissionPriority = MissionPriority.MEDIUM,
               metadata: Optional[Dict[str, Any]] = None) -> Mission:
        mission = Mission(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            state=MissionState.PENDING,
            priority=priority,
            workflow_ids=workflow_ids or [],
            metadata=metadata or {},
        )
        self._missions[mission.id] = mission
        return mission

    def get(self, mission_id: str) -> Optional[Mission]:
        return self._missions.get(mission_id)

    def list_missions(self) -> List[Mission]:
        return list(self._missions.values())

    def list_by_state(self, state: MissionState) -> List[Mission]:
        return [m for m in self._missions.values() if m.state == state]

    def update_state(self, mission_id: str, state: MissionState,
                     error: Optional[str] = None) -> Optional[Mission]:
        mission = self._missions.get(mission_id)
        if mission is None:
            return None
        mission.state = state
        if state == MissionState.RUNNING:
            mission.started_at = datetime.now(timezone.utc)
        if state.is_terminal:
            mission.completed_at = datetime.now(timezone.utc)
        if error:
            mission.error = error
        return mission

    def get_progress(self, mission_id: str,
                     completed_workflows: List[str],
                     failed_workflows: List[str],
                     running_workflow: Optional[str] = None) -> MissionProgress:
        mission = self._missions.get(mission_id)
        if mission is None:
            return MissionProgress()
        return MissionProgress(
            total_workflows=len(mission.workflow_ids),
            completed=len(completed_workflows),
            failed=len(failed_workflows),
            running=1 if running_workflow else 0,
            remaining=len(mission.workflow_ids) - len(completed_workflows) - len(failed_workflows),
        )

    def delete(self, mission_id: str) -> bool:
        if mission_id in self._missions:
            del self._missions[mission_id]
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._missions)
