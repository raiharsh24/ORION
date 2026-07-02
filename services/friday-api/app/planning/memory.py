import json
import os
import time
import tempfile
import shutil
from pathlib import Path
from dataclasses import asdict
from typing import Optional, List, Dict, Any
from collections import defaultdict

from app.planning.base import Plan, PlanStep


class PlanMemory:
    def __init__(self, base_path: Optional[str] = None):
        if base_path is None:
            base_path = os.path.join(
                tempfile.gettempdir(), ".planning_memory"
            )
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        (self._base_path / "plans").mkdir(parents=True, exist_ok=True)
        (self._base_path / "templates").mkdir(parents=True, exist_ok=True)

        self._cache: Dict[str, Plan] = {}
        self._statistics: Dict[str, Any] = {
            "total_saved": 0,
            "total_loaded": 0,
            "total_archived": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "template_matches": 0,
        }

    async def save_plan(self, plan: Plan) -> None:
        self._cache[plan.plan_id] = plan
        path = self._base_path / "plans" / f"{plan.plan_id}.json"
        data = self._plan_to_dict(plan)
        path.write_text(json.dumps(data, default=str, indent=2))
        self._statistics["total_saved"] += 1

    async def load_plan(self, plan_id: str) -> Optional[Plan]:
        if plan_id in self._cache:
            self._statistics["cache_hits"] += 1
            return self._cache[plan_id]

        path = self._base_path / "plans" / f"{plan_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
            plan = self._dict_to_plan(data)
            self._cache[plan_id] = plan
            self._statistics["total_loaded"] += 1
            return plan

        self._statistics["cache_misses"] += 1
        return None

    def cache_plan(self, plan: Plan) -> None:
        self._cache[plan.plan_id] = plan

    def get_cached(self, plan_id: str) -> Optional[Plan]:
        plan = self._cache.get(plan_id)
        if plan:
            self._statistics["cache_hits"] += 1
        else:
            self._statistics["cache_misses"] += 1
        return plan

    async def find_similar(self, goal_name: str,
                           goal_capabilities: Optional[List[str]] = None
                           ) -> List[Plan]:
        results: List[Plan] = []
        plans_dir = self._base_path / "plans"
        if not plans_dir.exists():
            return results

        goal_caps = set(goal_capabilities or [])
        for f in plans_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if data.get("goal_name", "").lower() == goal_name.lower():
                    plan = self._dict_to_plan(data)
                    results.append(plan)
                elif goal_caps and "metadata" in data:
                    plan_caps = set(data.get("metadata", {}).get(
                        "capabilities", []))
                    if plan_caps & goal_caps:
                        plan = self._dict_to_plan(data)
                        results.append(plan)
            except (json.JSONDecodeError, KeyError):
                continue
        return results

    async def store_template(self, template_id: str,
                              plan: Plan) -> None:
        path = self._base_path / "templates" / f"{template_id}.json"
        data = self._plan_to_dict(plan)
        data["_template_id"] = template_id
        path.write_text(json.dumps(data, default=str, indent=2))

    async def load_template(self, template_id: str) -> Optional[Plan]:
        path = self._base_path / "templates" / f"{template_id}.json"
        if path.exists():
            self._statistics["template_matches"] += 1
            data = json.loads(path.read_text())
            return self._dict_to_plan(data)
        return None

    async def archive_plan(self, plan_id: str) -> bool:
        plan = self._cache.pop(plan_id, None)
        path = self._base_path / "plans" / f"{plan_id}.json"
        if path.exists():
            archived = self._base_path / "plans" / f"{plan_id}.archived.json"
            path.rename(archived)
            self._statistics["total_archived"] += 1
            return True
        return False

    def get_statistics(self) -> Dict[str, Any]:
        return dict(self._statistics)

    async def clear(self) -> None:
        self._cache.clear()
        shutil.rmtree(self._base_path, ignore_errors=True)
        self._base_path.mkdir(parents=True, exist_ok=True)
        (self._base_path / "plans").mkdir(parents=True, exist_ok=True)
        (self._base_path / "templates").mkdir(parents=True, exist_ok=True)

    def _plan_to_dict(self, plan: Plan) -> Dict[str, Any]:
        return {
            "plan_id": plan.plan_id,
            "goal_id": plan.goal_id,
            "goal_name": plan.goal_name,
            "total_cost": plan.total_cost,
            "total_duration": plan.total_duration,
            "risk_score": plan.risk_score,
            "success_probability": plan.success_probability,
            "constraint_score": plan.constraint_score,
            "status": plan.status,
            "version": plan.version,
            "metadata": plan.metadata,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action_id": s.action_id,
                    "action_name": s.action_name,
                    "agent_id": s.agent_id,
                    "dependencies": s.dependencies,
                    "parallel_group": s.parallel_group,
                    "condition": s.condition,
                    "fallback_step_id": s.fallback_step_id,
                    "estimated_cost": s.estimated_cost,
                    "estimated_duration": s.estimated_duration,
                    "status": s.status,
                    "metadata": s.metadata,
                }
                for s in plan.steps
            ],
        }

    def _dict_to_plan(self, data: Dict[str, Any]) -> Plan:
        steps = [
            PlanStep(
                step_id=s["step_id"],
                action_id=s["action_id"],
                action_name=s.get("action_name", ""),
                agent_id=s.get("agent_id"),
                dependencies=s.get("dependencies", []),
                parallel_group=s.get("parallel_group"),
                condition=s.get("condition"),
                fallback_step_id=s.get("fallback_step_id"),
                estimated_cost=s.get("estimated_cost", 1.0),
                estimated_duration=s.get("estimated_duration", 1.0),
                status=s.get("status", "pending"),
                metadata=s.get("metadata", {}),
            )
            for s in data.get("steps", [])
        ]
        from datetime import datetime
        return Plan(
            plan_id=data["plan_id"],
            goal_id=data["goal_id"],
            goal_name=data.get("goal_name", ""),
            steps=steps,
            total_cost=data.get("total_cost", 0.0),
            total_duration=data.get("total_duration", 0.0),
            risk_score=data.get("risk_score", 0.0),
            success_probability=data.get("success_probability", 1.0),
            constraint_score=data.get("constraint_score", 1.0),
            status=data.get("status", "draft"),
            version=data.get("version", 1),
            metadata=data.get("metadata", {}),
        )
