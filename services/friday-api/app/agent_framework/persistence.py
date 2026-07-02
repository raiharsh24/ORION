import json
import os
import time
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any


@dataclass
class CheckpointData:
    agents: Dict[str, Any] = field(default_factory=dict)
    pending_tasks: List[Dict[str, Any]] = field(default_factory=list)
    delegation_tree: Dict[str, Any] = field(default_factory=dict)
    blackboard_data: Dict[str, Any] = field(default_factory=dict)
    context_data: Dict[str, Any] = field(default_factory=dict)
    scheduler_queues: List[Dict[str, Any]] = field(default_factory=list)
    metrics_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class PersistenceHealth:
    status: str = "healthy"
    has_checkpoint: bool = False
    stored_agents: int = 0
    total_files: int = 0


class PersistenceManager:
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            base_path = os.path.join(
                tempfile.gettempdir(), ".agent_framework_persistence"
            )
        self._base_path = Path(base_path)
        self._ensure_dirs()

    @property
    def base_path(self) -> Path:
        return self._base_path

    def _ensure_dirs(self) -> None:
        for subdir in ["agents", "tasks", "context", "blackboard", "metrics"]:
            (self._base_path / subdir).mkdir(parents=True, exist_ok=True)

    async def save_checkpoint(self, data: CheckpointData) -> None:
        path = self._base_path / "checkpoint.json"
        data.timestamp = time.time()
        path.write_text(json.dumps(asdict(data), default=str, indent=2))

    async def load_checkpoint(self) -> Optional[CheckpointData]:
        path = self._base_path / "checkpoint.json"
        if path.exists():
            raw = json.loads(path.read_text())
            return CheckpointData(**raw)
        return None

    async def save_agent_state(self, agent_id: str,
                               state_data: Dict[str, Any]) -> None:
        path = self._base_path / "agents" / f"{agent_id}.json"
        path.write_text(json.dumps(state_data, default=str, indent=2))

    async def load_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        path = self._base_path / "agents" / f"{agent_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    async def save_delegation_tree(self, tree_data: Dict[str, Any]) -> None:
        path = self._base_path / "tasks" / "delegation_tree.json"
        path.write_text(json.dumps(tree_data, default=str, indent=2))

    async def load_delegation_tree(self) -> Optional[Dict[str, Any]]:
        path = self._base_path / "tasks" / "delegation_tree.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    async def save_blackboard(self, data: Dict[str, Any]) -> None:
        path = self._base_path / "blackboard" / "data.json"
        path.write_text(json.dumps(data, default=str, indent=2))

    async def load_blackboard(self) -> Optional[Dict[str, Any]]:
        path = self._base_path / "blackboard" / "data.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    async def save_metrics(self, data: Dict[str, Any]) -> None:
        path = self._base_path / "metrics" / "data.json"
        path.write_text(json.dumps(data, default=str, indent=2))

    async def load_metrics(self) -> Optional[Dict[str, Any]]:
        path = self._base_path / "metrics" / "data.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    async def warm_restart(self) -> Optional[CheckpointData]:
        return await self.load_checkpoint()

    async def clear(self) -> None:
        shutil.rmtree(self._base_path, ignore_errors=True)
        self._ensure_dirs()

    async def checkpoint_exists(self) -> bool:
        return (self._base_path / "checkpoint.json").exists()

    async def count_files(self) -> int:
        count = 0
        for root, dirs, files in os.walk(str(self._base_path)):
            count += len(files)
        return count

    async def count_agent_files(self) -> int:
        agents_dir = self._base_path / "agents"
        if agents_dir.exists():
            return len(list(agents_dir.glob("*.json")))
        return 0

    def health(self) -> PersistenceHealth:
        has_cp = (self._base_path / "checkpoint.json").exists()
        agent_files = len(list((self._base_path / "agents").glob("*.json")))
        total = 0
        for root, dirs, files in os.walk(str(self._base_path)):
            total += len(files)
        return PersistenceHealth(
            status="healthy",
            has_checkpoint=has_cp,
            stored_agents=agent_files,
            total_files=total,
        )
