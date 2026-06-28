from typing import List, Optional, Dict
from app.missions.mission import Mission

class MissionHistory:
    """
    Storage interface for archiving and loading historical mission states.
    Implements an in-memory history provider.
    """
    def __init__(self, storage_path: Optional[str] = None) -> None:
        """
        Initialize the MissionHistory helper.
        """
        self._storage_path = storage_path
        self._history: Dict[str, Mission] = {}

    async def save(self, mission: Mission) -> bool:
        """
        Saves or updates a mission state to storage.

        Args:
            mission (Mission): Target mission model state.

        Returns:
            bool: True if saving succeeded.
        """
        self._history[mission.id] = mission
        return True

    async def load(self, mission_id: str) -> Optional[Mission]:
        """
        Loads a historically archived mission state by ID.

        Args:
            mission_id (str): Unique mission identifier.

        Returns:
            Optional[Mission]: Retrieved mission object, or None if not found.
        """
        return self._history.get(mission_id)

    async def list_history(self) -> List[Mission]:
        """
        Retrieves list of all saved mission histories.

        Returns:
            List[Mission]: All archived mission states.
        """
        return sorted(self._history.values(), key=lambda m: m.created_at)

    async def delete(self, mission_id: str) -> bool:
        """
        Deletes a specific mission history record.

        Args:
            mission_id (str): Unique mission identifier.

        Returns:
            bool: True if deleted successfully.
        """
        if mission_id in self._history:
            del self._history[mission_id]
            return True
        return False

    async def clear(self) -> None:
        """
        Deletes all historical records from storage path.
        """
        self._history.clear()
