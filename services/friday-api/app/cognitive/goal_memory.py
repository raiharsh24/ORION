import time
import uuid
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger

from app.cognitive.events import GoalCreated, GoalUpdated, MilestoneCompleted


@dataclass
class GoalRecord:
    goal_id: str
    objective: str
    description: str
    status: str = "active"
    parent_id: Optional[str] = None
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    progress_pct: float = 0.0
    priority: float = 5.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    description: str = ""
    status: str = "active"
    goals: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GoalMemory:
    def __init__(self, store: Any = None,
                 event_bus: Any = None) -> None:
        self._store = store
        self._event_bus = event_bus
        self._goals: Dict[str, GoalRecord] = {}
        self._projects: Dict[str, ProjectRecord] = {}
        self._on_save: Optional[Callable[[], None]] = None

    def set_on_save(self, callback: Callable[[], None]) -> None:
        self._on_save = callback

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass

    def _goals_key(self) -> str:
        return "cognitive:goals"

    def _projects_key(self) -> str:
        return "cognitive:projects"

    def _save_goals(self) -> None:
        if not self._store:
            return
        try:
            from app.memory.serializer import MemorySerializer
            data = {
                gid: {
                    "goal_id": g.goal_id,
                    "objective": g.objective,
                    "description": g.description,
                    "status": g.status,
                    "parent_id": g.parent_id,
                    "milestones": g.milestones,
                    "progress_pct": g.progress_pct,
                    "priority": g.priority,
                    "created_at": g.created_at,
                    "updated_at": g.updated_at,
                    "completed_at": g.completed_at,
                    "tags": g.tags,
                    "metadata": g.metadata,
                }
                for gid, g in self._goals.items()
            }
            self._store.put(self._goals_key(), data)
        except Exception:
            pass

    def _load_goals(self) -> None:
        if not self._store:
            return
        try:
            data = self._store.get(self._goals_key())
            if data:
                for gid, gd in data.items():
                    self._goals[gid] = GoalRecord(**gd)
        except Exception:
            pass

    def _save_projects(self) -> None:
        if not self._store:
            return
        try:
            from app.memory.serializer import MemorySerializer
            data = {
                pid: {
                    "project_id": p.project_id,
                    "name": p.name,
                    "description": p.description,
                    "status": p.status,
                    "goals": p.goals,
                    "tags": p.tags,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "metadata": p.metadata,
                }
                for pid, p in self._projects.items()
            }
            self._store.put(self._projects_key(), data)
        except Exception:
            pass

    def _load_projects(self) -> None:
        if not self._store:
            return
        try:
            data = self._store.get(self._projects_key())
            if data:
                for pid, pd in data.items():
                    self._projects[pid] = ProjectRecord(**pd)
        except Exception:
            pass

    def load(self) -> None:
        self._load_goals()
        self._load_projects()

    def save(self) -> None:
        self._save_goals()
        self._save_projects()
        if self._on_save:
            try:
                self._on_save()
            except Exception:
                pass

    def create_goal(self, objective: str, description: str = "",
                    parent_id: Optional[str] = None,
                    priority: float = 5.0,
                    tags: Optional[List[str]] = None) -> GoalRecord:
        goal = GoalRecord(
            goal_id=str(uuid.uuid4()),
            objective=objective,
            description=description or objective,
            parent_id=parent_id,
            priority=priority,
            tags=tags or [],
        )
        self._goals[goal.goal_id] = goal
        self._save_goals()
        self._publish(GoalCreated(
            goal_id=goal.goal_id, objective=objective,
            parent_id=parent_id, priority=priority,
        ))
        logger.info(f"GoalMemory: Created goal '{goal.goal_id[:8]}' -> '{objective[:60]}'")
        return goal

    def update_goal(self, goal_id: str, **updates: Any) -> Optional[GoalRecord]:
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        for key, value in updates.items():
            if hasattr(goal, key):
                setattr(goal, key, value)
        goal.updated_at = time.time()
        if updates.get("status") in ("completed", "failed", "cancelled"):
            goal.completed_at = time.time()
        self._save_goals()
        self._publish(GoalUpdated(
            goal_id=goal_id, objective=goal.objective,
            status=goal.status, progress_pct=goal.progress_pct,
        ))
        return goal

    def get_goal(self, goal_id: str) -> Optional[GoalRecord]:
        return self._goals.get(goal_id)

    def list_goals(self, status: Optional[str] = None,
                   parent_id: Optional[str] = None,
                   tag: Optional[str] = None) -> List[GoalRecord]:
        results = list(self._goals.values())
        if status:
            results = [g for g in results if g.status == status]
        if parent_id is not None:
            results = [g for g in results if g.parent_id == parent_id]
        elif parent_id == "":
            results = [g for g in results if g.parent_id is None]
        if tag:
            results = [g for g in results if tag in g.tags]
        return sorted(results, key=lambda g: (-g.priority, g.created_at))

    def add_milestone(self, goal_id: str, name: str,
                      description: str = "") -> Optional[Dict[str, Any]]:
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        milestone = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": description,
            "completed": False,
            "created_at": time.time(),
        }
        goal.milestones.append(milestone)
        goal.updated_at = time.time()
        self._save_goals()
        return milestone

    def complete_milestone(self, goal_id: str, milestone_id: str) -> bool:
        goal = self._goals.get(goal_id)
        if not goal:
            return False
        for m in goal.milestones:
            if m["id"] == milestone_id:
                m["completed"] = True
                m["completed_at"] = time.time()
                goal.updated_at = time.time()
                completed = sum(1 for ms in goal.milestones if ms["completed"])
                goal.progress_pct = (completed / len(goal.milestones)) * 100 if goal.milestones else 100.0
                self._save_goals()
                self._publish(MilestoneCompleted(
                    goal_id=goal_id, milestone_id=milestone_id,
                    milestone_name=m["name"], progress_pct=goal.progress_pct,
                ))
                return True
        return False

    def create_project(self, name: str, description: str = "",
                       tags: Optional[List[str]] = None) -> ProjectRecord:
        project = ProjectRecord(
            project_id=str(uuid.uuid4()),
            name=name,
            description=description,
            tags=tags or [],
        )
        self._projects[project.project_id] = project
        self._save_projects()
        return project

    def get_project(self, project_id: str) -> Optional[ProjectRecord]:
        return self._projects.get(project_id)

    def list_projects(self, status: Optional[str] = None) -> List[ProjectRecord]:
        results = list(self._projects.values())
        if status:
            results = [p for p in results if p.status == status]
        return results

    def add_goal_to_project(self, project_id: str, goal_id: str) -> bool:
        project = self._projects.get(project_id)
        if not project:
            return False
        if goal_id not in project.goals:
            project.goals.append(goal_id)
            project.updated_at = time.time()
            self._save_projects()
        return True

    def search_goals(self, query: str) -> List[GoalRecord]:
        q = query.lower()
        results = []
        for g in self._goals.values():
            if (q in g.objective.lower()
                    or q in g.description.lower()
                    or any(q in t.lower() for t in g.tags)):
                results.append(g)
        return sorted(results, key=lambda g: (-g.priority, g.created_at))

    def get_strategic_context(self) -> Dict[str, Any]:
        active = [g for g in self._goals.values() if g.status == "active"]
        completed = [g for g in self._goals.values() if g.status == "completed"]
        return {
            "total_goals": len(self._goals),
            "active_goals": len(active),
            "completed_goals": len(completed),
            "failed_goals": sum(1 for g in self._goals.values() if g.status == "failed"),
            "projects": len(self._projects),
            "top_priorities": sorted(
                active, key=lambda g: (-g.priority, g.created_at)
            )[:5],
            "unfinished": [
                {"goal_id": g.goal_id, "objective": g.objective[:100],
                 "progress": g.progress_pct}
                for g in active if g.progress_pct < 100.0
            ],
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "goals_stored": len(self._goals),
            "projects_stored": len(self._projects),
            "active_goals": sum(1 for g in self._goals.values() if g.status == "active"),
            "completed_goals": sum(1 for g in self._goals.values() if g.status == "completed"),
        }
