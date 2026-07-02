import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


@dataclass
class MissionRecord:
    mission_id: str
    user_request: str
    intent: str = ""
    status: str = "created"
    stage_names: List[str] = field(default_factory=list)
    stage_statuses: Dict[str, str] = field(default_factory=dict)
    stage_errors: Dict[str, Optional[str]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    plan_id: Optional[str] = None
    goal_ids: List[str] = field(default_factory=list)
    assigned_agents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def from_mission(cls, mission: Any) -> "MissionRecord":
        stage_names = [s.name for s in getattr(mission, "stages", [])]
        stage_statuses = {s.name: s.status for s in getattr(mission, "stages", [])}
        stage_errors = {s.name: s.error for s in getattr(mission, "stages", [])}
        return cls(
            mission_id=mission.mission_id,
            user_request=mission.user_request,
            intent=getattr(mission, "intent", ""),
            status=mission.status,
            stage_names=stage_names,
            stage_statuses=stage_statuses,
            stage_errors=stage_errors,
            created_at=str(mission.created_at) if getattr(mission, "created_at", None) else "",
            updated_at=str(mission.updated_at) if getattr(mission, "updated_at", None) else "",
            completed_at=str(mission.completed_at) if getattr(mission, "completed_at", None) else None,
            plan_id=getattr(mission, "plan_id", None),
            goal_ids=getattr(mission, "goal_ids", []),
            assigned_agents=getattr(mission, "assigned_agents", []),
            metadata=getattr(mission, "metadata", {}),
            error=getattr(mission, "error", None),
        )


@dataclass
class TelemetryRecord:
    mission_id: str
    intent: str = ""
    total_duration_ms: float = 0.0
    planning_latency_ms: float = 0.0
    resolution_latency_ms: float = 0.0
    execution_latency_ms: float = 0.0
    reflection_latency_ms: float = 0.0
    retry_count: int = 0
    recovery_count: int = 0
    success: bool = True
    failure_stage: str = ""
    failure_reason: str = ""

    @classmethod
    def from_telemetry(cls, tel: Any) -> "TelemetryRecord":
        if tel is None:
            return cls(mission_id="")
        return cls(
            mission_id=getattr(tel, "mission_id", ""),
            intent=getattr(tel, "intent", ""),
            total_duration_ms=getattr(tel, "total_duration_ms", 0.0),
            planning_latency_ms=getattr(tel, "planning_latency_ms", 0.0),
            resolution_latency_ms=getattr(tel, "resolution_latency_ms", 0.0),
            execution_latency_ms=getattr(tel, "execution_latency_ms", 0.0),
            reflection_latency_ms=getattr(tel, "reflection_latency_ms", 0.0),
            retry_count=getattr(tel, "retry_count", 0),
            recovery_count=getattr(tel, "recovery_count", 0),
            success=getattr(tel, "success", True),
            failure_stage=getattr(tel, "failure_stage", ""),
            failure_reason=getattr(tel, "failure_reason", ""),
        )


@dataclass
class CheckpointRecord:
    mission_id: str
    stage: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class MissionStore:
    def __init__(self, base_path: Optional[str] = None):
        self._base_path = base_path or os.path.join(
            os.path.expanduser("~"), ".friday", "missions")
        os.makedirs(self._base_path, exist_ok=True)
        self._cache: Dict[str, MissionRecord] = {}

    def _mission_path(self, mission_id: str) -> str:
        return os.path.join(self._base_path, f"{mission_id}.json")

    def _telemetry_path(self, mission_id: str) -> str:
        return os.path.join(self._base_path, f"{mission_id}_telemetry.json")

    def _checkpoint_path(self, mission_id: str) -> str:
        return os.path.join(self._base_path, f"{mission_id}_checkpoint.json")

    def _reflection_path(self, mission_id: str) -> str:
        return os.path.join(self._base_path, f"{mission_id}_reflection.json")

    def save_mission(self, mission: Any) -> None:
        record = MissionRecord.from_mission(mission)
        path = self._mission_path(mission.mission_id)
        with open(path, "w") as f:
            json.dump(asdict(record), f, indent=2, default=str)
        self._cache[mission.mission_id] = record

    def load_mission(self, mission_id: str) -> Optional[MissionRecord]:
        if mission_id in self._cache:
            return self._cache[mission_id]
        path = self._mission_path(mission_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        record = MissionRecord(**data)
        self._cache[mission_id] = record
        return record

    def list_missions(self) -> List[str]:
        mission_ids: List[str] = []
        if os.path.isdir(self._base_path):
            for fname in os.listdir(self._base_path):
                if fname.endswith(".json") and "_" not in fname:
                    mission_ids.append(fname.replace(".json", ""))
        return mission_ids

    def delete_mission(self, mission_id: str) -> bool:
        paths = [
            self._mission_path(mission_id),
            self._telemetry_path(mission_id),
            self._checkpoint_path(mission_id),
            self._reflection_path(mission_id),
        ]
        found = False
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
                found = True
        self._cache.pop(mission_id, None)
        return found

    def save_telemetry(self, mission_id: str, tel: Any) -> None:
        record = TelemetryRecord.from_telemetry(tel)
        record.mission_id = mission_id
        path = self._telemetry_path(mission_id)
        with open(path, "w") as f:
            json.dump(asdict(record), f, indent=2, default=str)

    def load_telemetry(self, mission_id: str) -> Optional[TelemetryRecord]:
        path = self._telemetry_path(mission_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        return TelemetryRecord(**data)

    def save_checkpoint(self, mission_id: str, stage: str,
                         data: Optional[Dict[str, Any]] = None) -> None:
        record = CheckpointRecord(
            mission_id=mission_id,
            stage=stage,
            data=data or {},
            timestamp=time.time(),
        )
        path = self._checkpoint_path(mission_id)
        with open(path, "w") as f:
            json.dump(asdict(record), f, indent=2, default=str)

    def load_checkpoint(self, mission_id: str) -> Optional[CheckpointRecord]:
        path = self._checkpoint_path(mission_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        return CheckpointRecord(**data)

    def save_reflection(self, mission_id: str,
                         report: Any) -> None:
        data = {
            "mission_id": mission_id,
            "total_duration_ms": getattr(report, "total_duration_ms", 0.0),
            "bottlenecks": getattr(report, "bottlenecks", []),
            "lessons": [
                {"category": l.category, "description": l.description,
                 "severity": l.severity, "recommendation": l.recommendation}
                for l in getattr(report, "lessons", [])
            ],
            "stages_completed": getattr(report, "stages_completed", 0),
        }
        path = self._reflection_path(mission_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load_reflection(self, mission_id: str) -> Optional[Dict[str, Any]]:
        path = self._reflection_path(mission_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def load_all_active(self) -> List[MissionRecord]:
        active: List[MissionRecord] = []
        for mission_id in self.list_missions():
            record = self.load_mission(mission_id)
            if record and record.status in ("created", "planning", "waiting",
                                             "ready", "running", "paused",
                                             "recovering"):
                active.append(record)
        return active
