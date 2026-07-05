import uuid
import json
import os
import sqlite3
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from loguru import logger

from app.mission_engine.base import (
    Mission, MissionState, MissionPriority, MissionProgress,
)


class MissionStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self._missions: Dict[str, Mission] = {}
        self._lock = threading.Lock()
        if db_path:
            self._db_path = db_path
            self._init_db()
            self._load_from_db()

    def _init_db(self) -> None:
        from app.kernel.migrate import run_database_migrations
        with self._lock:
            run_database_migrations(self._db_path)

    def _load_from_db(self) -> None:
        if not os.path.exists(self._db_path):
            return
        with self._lock:
            conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10.0)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, data FROM missions")
                for row_id, data_json in cursor.fetchall():
                    try:
                        data = json.loads(data_json)
                        mission = Mission(**data)
                        self._missions[row_id] = mission
                    except Exception as e:
                        logger.error(f"Failed to load mission {row_id}: {e}")
                if self._missions:
                    logger.info(f"Loaded {len(self._missions)} missions from {self._db_path}")
            finally:
                conn.close()

    def _persist(self, mission_id: str) -> None:
        if not hasattr(self, '_db_path') or not self._db_path:
            return
        mission = self._missions.get(mission_id)
        if mission is None:
            return
        with self._lock:
            conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10.0)
            try:
                cursor = conn.cursor()
                data = mission.model_dump_json()
                cursor.execute(
                    "INSERT OR REPLACE INTO missions (id, data) VALUES (?, ?)",
                    (mission_id, data),
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to persist mission {mission_id}: {e}")
            finally:
                conn.close()

    def _remove_from_db(self, mission_id: str) -> None:
        if not hasattr(self, '_db_path') or not self._db_path:
            return
        with self._lock:
            conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10.0)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to remove mission {mission_id} from db: {e}")
            finally:
                conn.close()

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
        self._persist(mission.id)
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
        self._persist(mission_id)
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
            self._remove_from_db(mission_id)
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._missions)
