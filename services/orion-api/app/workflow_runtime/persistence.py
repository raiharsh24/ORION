import os
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone
from loguru import logger

from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeWorkflowStatus, RuntimeStepStatus
)


LOCK_SUFFIX = ".lock"
LOCK_TIMEOUT = 5.0


class WorkflowPersistence:
    def __init__(self, persist_dir: str) -> None:
        self._persist_dir = persist_dir
        self._workflows_dir = os.path.join(persist_dir, "workflows")
        os.makedirs(self._workflows_dir, exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}
        logger.info(f"WorkflowPersistence initialized at {self._workflows_dir}")

    def _path(self, workflow_id: str) -> str:
        return os.path.join(self._workflows_dir, f"{workflow_id}.json")

    def _get_lock(self, workflow_id: str) -> asyncio.Lock:
        if workflow_id not in self._locks:
            self._locks[workflow_id] = asyncio.Lock()
        return self._locks[workflow_id]

    async def save(self, workflow: RuntimeWorkflow) -> None:
        workflow.updated_at = datetime.now(timezone.utc)
        lock = self._get_lock(workflow.workflow_id)
        async with lock:
            file_path = self._path(workflow.workflow_id)
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(workflow.model_dump(mode="json"), f, indent=2, default=str)
                logger.debug(f"WorkflowPersistence: saved '{workflow.workflow_id}' ({workflow.status.value})")
            except Exception as e:
                logger.error(f"WorkflowPersistence: save failed for '{workflow.workflow_id}': {e}")

    async def load(self, workflow_id: str) -> Optional[RuntimeWorkflow]:
        file_path = self._path(workflow_id)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return RuntimeWorkflow(**data)
        except Exception as e:
            logger.error(f"WorkflowPersistence: load failed for '{workflow_id}': {e}")
            return None

    async def list(self) -> List[RuntimeWorkflow]:
        workflows = []
        if not os.path.isdir(self._workflows_dir):
            return workflows
        for filename in os.listdir(self._workflows_dir):
            if filename.endswith(".json"):
                wf_id = filename[:-5]
                wf = await self.load(wf_id)
                if wf:
                    workflows.append(wf)
        return workflows

    async def delete(self, workflow_id: str) -> bool:
        file_path = self._path(workflow_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self._locks.pop(workflow_id, None)
                logger.info(f"WorkflowPersistence: deleted '{workflow_id}'")
                return True
            except Exception as e:
                logger.error(f"WorkflowPersistence: delete failed for '{workflow_id}': {e}")
        return False

    async def recover_incomplete(self) -> List[RuntimeWorkflow]:
        incomplete = []
        workflows = await self.list()
        for wf in workflows:
            if wf.status in (
                RuntimeWorkflowStatus.RUNNING,
                RuntimeWorkflowStatus.PAUSED,
                RuntimeWorkflowStatus.PENDING,
            ):
                if wf.status == RuntimeWorkflowStatus.RUNNING:
                    for step in wf.steps.values():
                        if step.status == RuntimeStepStatus.RUNNING:
                            step.status = RuntimeStepStatus.PENDING
                wf.status = RuntimeWorkflowStatus.PAUSED
                await self.save(wf)
                incomplete.append(wf)
                logger.info(f"WorkflowPersistence: recovered '{wf.workflow_id}' as PAUSED")
        return incomplete

    async def list_by_status(self, status: RuntimeWorkflowStatus) -> List[RuntimeWorkflow]:
        return [wf for wf in await self.list() if wf.status == status]

    def count(self) -> int:
        if not os.path.isdir(self._workflows_dir):
            return 0
        return len([f for f in os.listdir(self._workflows_dir) if f.endswith(".json")])

    def health(self) -> Dict:
        return {
            "status": "HEALTHY",
            "message": "WorkflowPersistence operational.",
            "details": {
                "persist_dir": self._workflows_dir,
                "stored_workflows": self.count()
            }
        }
