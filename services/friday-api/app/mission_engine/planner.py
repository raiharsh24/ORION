from typing import Dict, List, Any, Optional
from app.workflow_engine.base import WorkflowGraph
from app.workflow_engine.graph import WorkflowGraphBuilder, WorkflowValidator
from app.mission_engine.base import Mission, MissionPriority, MissionState
from app.mission_engine.mission import MissionStore


class MissionPlanner:
    def __init__(self, mission_store: MissionStore) -> None:
        self._store = mission_store

    def create_mission(
        self,
        name: str,
        description: str = "",
        workflow_graphs: Optional[Dict[str, WorkflowGraph]] = None,
        workflow_ids: Optional[List[str]] = None,
        priority: MissionPriority = MissionPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Mission:
        if workflow_graphs:
            wf_ids: List[str] = []
            for wf_id, graph in workflow_graphs.items():
                errors = WorkflowValidator.validate(graph)
                if errors:
                    raise ValueError(
                        f"Workflow '{wf_id}' validation failed: {errors[0]}"
                    )
                wf_ids.append(wf_id)
            final_ids = wf_ids
        else:
            final_ids = workflow_ids or []

        return self._store.create(
            name=name,
            description=description,
            workflow_ids=final_ids,
            priority=priority,
            metadata=metadata,
        )

    def plan_sequential(
        self,
        mission: Mission,
        graphs: Dict[str, WorkflowGraph],
    ) -> List[str]:
        order = []
        for wf_id in mission.workflow_ids:
            order.append(wf_id)
        return order
