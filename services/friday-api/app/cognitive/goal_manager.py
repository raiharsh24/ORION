import time
import uuid
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class GoalNode:
    goal_id: str
    objective: str
    description: str = ""
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    priority: float = 5.0
    estimated_duration_ms: float = 0.0
    actual_duration_ms: float = 0.0
    progress_pct: float = 0.0
    depends_on: List[str] = field(default_factory=list)
    mission_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class GoalHierarchy:
    root_id: str
    nodes: Dict[str, GoalNode] = field(default_factory=dict)

    @property
    def depth(self) -> int:
        return self._max_depth(self.root_id, 0)

    def _max_depth(self, node_id: str, depth: int) -> int:
        node = self.nodes.get(node_id)
        if not node or not node.children:
            return depth
        return max(self._max_depth(c, depth + 1) for c in node.children)


class HierarchicalGoalManager:
    def __init__(self, goal_memory: Any = None,
                 goal_planner: Any = None) -> None:
        self._goal_memory = goal_memory
        self._goal_planner = goal_planner
        self._hierarchies: Dict[str, GoalHierarchy] = {}

    def create_hierarchy(self, objective: str,
                         description: str = "",
                         priority: float = 5.0) -> GoalHierarchy:
        root = GoalNode(
            goal_id=str(uuid.uuid4()),
            objective=objective,
            description=description or objective,
            priority=priority,
            status="active",
        )
        if self._goal_memory:
            record = self._goal_memory.create_goal(
                objective=objective, description=description,
                priority=priority,
            )
            root.metadata["memory_goal_id"] = record.goal_id

        hierarchy = GoalHierarchy(root_id=root.goal_id)
        hierarchy.nodes[root.goal_id] = root
        self._hierarchies[root.goal_id] = hierarchy
        logger.info(
            f"HierarchicalGoalManager: Created hierarchy '{root.goal_id[:8]}'"
        )
        return hierarchy

    def add_sub_goal(self, hierarchy_id: str,
                     parent_id: str,
                     objective: str,
                     description: str = "",
                     priority: float = 5.0,
                     depends_on: Optional[List[str]] = None) -> Optional[GoalNode]:
        hierarchy = self._hierarchies.get(hierarchy_id)
        if not hierarchy:
            return None
        parent = hierarchy.nodes.get(parent_id)
        if not parent:
            return None

        node = GoalNode(
            goal_id=str(uuid.uuid4()),
            objective=objective,
            description=description or objective,
            parent_id=parent_id,
            priority=priority,
            depends_on=depends_on or [],
            status="pending",
        )

        if self._goal_memory:
            record = self._goal_memory.create_goal(
                objective=objective, description=description,
                parent_id=hierarchy_id, priority=priority,
            )
            node.metadata["memory_goal_id"] = record.goal_id

        parent.children.append(node.goal_id)
        hierarchy.nodes[node.goal_id] = node
        logger.info(
            f"HierarchicalGoalManager: Sub-goal '{node.goal_id[:8]}' "
            f"under '{parent_id[:8]}'"
        )
        return node

    def analyze_and_decompose(self, objective: str,
                               description: str = "",
                               depth: int = 2) -> GoalHierarchy:
        hierarchy = self.create_hierarchy(objective, description)
        if self._goal_planner:
            try:
                analysis = self._goal_planner.analyze_objective(objective)
                capabilities = analysis.get("capabilities", [])
                for cap in capabilities:
                    sub = self.add_sub_goal(
                        hierarchy_id=hierarchy.root_id,
                        parent_id=hierarchy.root_id,
                        objective=f"{cap.replace('_', ' ').title()} for: {objective[:60]}",
                        description=f"Execute {cap} step",
                        priority=5.0,
                    )
                    if sub and depth > 1 and cap in ("code_generation", "research", "analysis"):
                        self._add_leaf_goals(hierarchy, sub.goal_id, cap, depth - 1)
            except Exception:
                pass
        return hierarchy

    def _add_leaf_goals(self, hierarchy: GoalHierarchy,
                         parent_id: str, capability: str,
                         remaining_depth: int) -> None:
        if remaining_depth <= 0:
            return
        leaf_templates = {
            "code_generation": [
                "Design architecture",
                "Implement core logic",
                "Write tests",
                "Review and refactor",
            ],
            "research": [
                "Gather sources",
                "Analyze findings",
                "Synthesize report",
            ],
            "analysis": [
                "Collect data",
                "Run analysis",
                "Generate insights",
            ],
        }
        templates = leaf_templates.get(capability, ["Execute step"])
        for t in templates:
            self.add_sub_goal(
                hierarchy_id=hierarchy.root_id,
                parent_id=parent_id,
                objective=t,
                priority=4.0,
            )

    def get_ready_goals(self, hierarchy_id: str) -> List[GoalNode]:
        hierarchy = self._hierarchies.get(hierarchy_id)
        if not hierarchy:
            return []
        ready = []
        for node in hierarchy.nodes.values():
            if node.status != "pending":
                continue
            if all(self._is_dependency_satisfied(hierarchy, dep)
                   for dep in node.depends_on):
                ready.append(node)
        return sorted(ready, key=lambda n: (-n.priority, n.created_at))

    def _is_dependency_satisfied(self, hierarchy: GoalHierarchy,
                                  dep_id: str) -> bool:
        dep = hierarchy.nodes.get(dep_id)
        if not dep:
            return True
        return dep.status == "completed"

    def update_goal_status(self, hierarchy_id: str, goal_id: str,
                           status: str, progress_pct: Optional[float] = None,
                           duration_ms: float = 0.0) -> bool:
        hierarchy = self._hierarchies.get(hierarchy_id)
        if not hierarchy:
            return False
        node = hierarchy.nodes.get(goal_id)
        if not node:
            return False
        node.status = status
        node.updated_at = time.time()
        if progress_pct is not None:
            node.progress_pct = min(100.0, progress_pct)
        if duration_ms > 0:
            node.actual_duration_ms = duration_ms
        if status in ("completed", "failed", "cancelled"):
            node.completed_at = time.time()
            if status == "completed":
                node.progress_pct = 100.0

        if self._goal_memory:
            self._goal_memory.update_goal(
                node.metadata.get("memory_goal_id", goal_id),
                status=status, progress_pct=node.progress_pct,
            )

        self._update_parent_progress(hierarchy, node.parent_id)
        return True

    def _update_parent_progress(self, hierarchy: GoalHierarchy,
                                 parent_id: Optional[str]) -> None:
        if not parent_id:
            return
        parent = hierarchy.nodes.get(parent_id)
        if not parent or not parent.children:
            return
        children_statuses = [
            hierarchy.nodes.get(cid) for cid in parent.children
            if hierarchy.nodes.get(cid)
        ]
        if not children_statuses:
            return
        completed = sum(1 for c in children_statuses if c.status == "completed")
        total = len(children_statuses)
        parent.progress_pct = round((completed / total) * 100, 1) if total > 0 else 0.0
        parent.updated_at = time.time()

        if all(c.status == "completed" for c in children_statuses):
            parent.status = "completed"
            parent.completed_at = time.time()

        self._update_parent_progress(hierarchy, parent.parent_id)

    def link_to_mission(self, hierarchy_id: str, goal_id: str,
                        mission_id: str) -> bool:
        hierarchy = self._hierarchies.get(hierarchy_id)
        if not hierarchy:
            return False
        node = hierarchy.nodes.get(goal_id)
        if not node:
            return False
        if mission_id not in node.mission_ids:
            node.mission_ids.append(mission_id)
        return True

    def get_hierarchy(self, hierarchy_id: str) -> Optional[GoalHierarchy]:
        return self._hierarchies.get(hierarchy_id)

    def get_sub_tree(self, hierarchy_id: str,
                     root_id: str) -> Optional[GoalHierarchy]:
        hierarchy = self._hierarchies.get(hierarchy_id)
        if not hierarchy:
            return None
        root = hierarchy.nodes.get(root_id)
        if not root:
            return None
        sub = GoalHierarchy(root_id=root_id)
        self._collect_subtree(hierarchy, root_id, sub)
        return sub

    def _collect_subtree(self, source: GoalHierarchy,
                          node_id: str, target: GoalHierarchy) -> None:
        node = source.nodes.get(node_id)
        if not node:
            return
        target.nodes[node_id] = node
        for child_id in node.children:
            self._collect_subtree(source, child_id, target)

    def get_pending_chain(self, hierarchy_id: str) -> List[GoalNode]:
        hierarchy = self._hierarchies.get(hierarchy_id)
        if not hierarchy:
            return []
        pending = []
        self._collect_pending(hierarchy, hierarchy.root_id, pending)
        return pending

    def _collect_pending(self, hierarchy: GoalHierarchy,
                          node_id: str, result: List[GoalNode]) -> None:
        node = hierarchy.nodes.get(node_id)
        if not node:
            return
        if node.status in ("pending", "active"):
            result.append(node)
        for child_id in node.children:
            self._collect_pending(hierarchy, child_id, result)

    def get_stats(self) -> Dict[str, Any]:
        total_nodes = sum(len(h.nodes) for h in self._hierarchies.values())
        total_active = sum(
            1 for h in self._hierarchies.values()
            for n in h.nodes.values() if n.status == "active"
        )
        total_completed = sum(
            1 for h in self._hierarchies.values()
            for n in h.nodes.values() if n.status == "completed"
        )
        return {
            "hierarchies": len(self._hierarchies),
            "total_nodes": total_nodes,
            "active_nodes": total_active,
            "completed_nodes": total_completed,
            "avg_depth": round(
                sum(h.depth for h in self._hierarchies.values())
                / max(len(self._hierarchies), 1), 1
            ),
        }
