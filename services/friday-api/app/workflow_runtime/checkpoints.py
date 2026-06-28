import os
import json
from typing import Dict, Any, Optional
from loguru import logger


class CheckpointManager:
    def __init__(self, persist_dir: str) -> None:
        self._checkpoints_dir = os.path.join(persist_dir, "checkpoints")
        os.makedirs(self._checkpoints_dir, exist_ok=True)

    def _path(self, workflow_id: str, step_id: str) -> str:
        return os.path.join(self._checkpoints_dir, f"{workflow_id}_{step_id}.json")

    async def save_checkpoint(
        self,
        workflow_id: str,
        step_id: str,
        data: Dict[str, Any]
    ) -> None:
        file_path = self._path(workflow_id, step_id)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            logger.debug(f"Checkpoint saved: {workflow_id}/{step_id}")
        except Exception as e:
            logger.error(f"Checkpoint save failed: {workflow_id}/{step_id}: {e}")

    async def load_checkpoint(
        self,
        workflow_id: str,
        step_id: str
    ) -> Optional[Dict[str, Any]]:
        file_path = self._path(workflow_id, step_id)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Checkpoint load failed: {workflow_id}/{step_id}: {e}")
            return None

    async def clear_checkpoint(self, workflow_id: str, step_id: str) -> None:
        file_path = self._path(workflow_id, step_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Checkpoint clear failed: {workflow_id}/{step_id}: {e}")

    async def clear_workflow_checkpoints(self, workflow_id: str) -> None:
        if not os.path.isdir(self._checkpoints_dir):
            return
        count = 0
        for filename in os.listdir(self._checkpoints_dir):
            if filename.startswith(f"{workflow_id}_"):
                try:
                    os.remove(os.path.join(self._checkpoints_dir, filename))
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to clear checkpoint {filename}: {e}")
        if count:
            logger.info(f"Cleared {count} checkpoints for workflow '{workflow_id}'")

    def health(self) -> Dict:
        count = 0
        if os.path.isdir(self._checkpoints_dir):
            count = len(os.listdir(self._checkpoints_dir))
        return {
            "status": "HEALTHY",
            "details": {"checkpoints_dir": self._checkpoints_dir, "checkpoint_count": count}
        }
