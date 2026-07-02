from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from app.mission_engine.base import (
    Mission, MissionState, MissionContext, MissionCheckpoint,
    MissionProgress,
)


class CheckpointManager:
    def __init__(self) -> None:
        self._checkpoints: Dict[str, MissionCheckpoint] = {}
        self._checkpoint_count = 0

    async def save(self, mission: Mission, context: MissionContext,
                   completed: List[str], failed: List[str],
                   running: Optional[str] = None) -> MissionCheckpoint:
        cp = MissionCheckpoint(
            mission_id=mission.id,
            mission_state=mission.state,
            completed_workflows=list(completed),
            failed_workflows=list(failed),
            running_workflow=running,
            context=context,
        )
        self._checkpoints[cp.id] = cp
        self._checkpoint_count += 1
        return cp

    def load(self, checkpoint_id: str) -> Optional[MissionCheckpoint]:
        return self._checkpoints.get(checkpoint_id)

    def get_mission_checkpoints(self, mission_id: str) -> List[MissionCheckpoint]:
        return [c for c in self._checkpoints.values() if c.mission_id == mission_id]

    def get_latest_checkpoint(self, mission_id: str) -> Optional[MissionCheckpoint]:
        cps = self.get_mission_checkpoints(mission_id)
        if not cps:
            return None
        return max(cps, key=lambda c: c.timestamp)

    def delete_mission_checkpoints(self, mission_id: str) -> None:
        self._checkpoints = {
            cid: cp for cid, cp in self._checkpoints.items()
            if cp.mission_id != mission_id
        }

    async def recover(self, mission: Mission,
                      checkpoint: MissionCheckpoint) -> MissionContext:
        mission.state = checkpoint.mission_state
        ctx = checkpoint.context or MissionContext(mission_id=mission.id)
        return ctx

    @property
    def checkpoint_count(self) -> int:
        return self._checkpoint_count
