from app.events.events import OrionEvent


class WorkflowStarted(OrionEvent):
    def __init__(self, workflow_id: str, name: str, total_steps: int) -> None:
        super().__init__(topic="WorkflowStarted", data={
            "workflow_id": workflow_id, "name": name, "total_steps": total_steps
        })

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]

    @property
    def workflow_name(self) -> str:
        return self.data["name"]

    @property
    def total_steps(self) -> int:
        return self.data["total_steps"]


class WorkflowPaused(OrionEvent):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(topic="WorkflowPaused", data={"workflow_id": workflow_id})

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]


class WorkflowResumed(OrionEvent):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(topic="WorkflowResumed", data={"workflow_id": workflow_id})

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]


class WorkflowStepStarted(OrionEvent):
    def __init__(self, workflow_id: str, step_id: str, step_name: str, step_type: str) -> None:
        super().__init__(topic="WorkflowStepStarted", data={
            "workflow_id": workflow_id, "step_id": step_id,
            "step_name": step_name, "step_type": step_type
        })

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]

    @property
    def step_id(self) -> str:
        return self.data["step_id"]

    @property
    def step_name(self) -> str:
        return self.data["step_name"]

    @property
    def step_type(self) -> str:
        return self.data["step_type"]


class WorkflowStepCompleted(OrionEvent):
    def __init__(self, workflow_id: str, step_id: str, success: bool = True) -> None:
        super().__init__(topic="WorkflowStepCompleted", data={
            "workflow_id": workflow_id, "step_id": step_id, "success": success
        })

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]

    @property
    def step_id(self) -> str:
        return self.data["step_id"]

    @property
    def success(self) -> bool:
        return self.data["success"]


class WorkflowFailed(OrionEvent):
    def __init__(self, workflow_id: str, error: str) -> None:
        super().__init__(topic="WorkflowFailed", data={
            "workflow_id": workflow_id, "error": error
        })

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]

    @property
    def error(self) -> str:
        return self.data["error"]


class WorkflowCompleted(OrionEvent):
    def __init__(self, workflow_id: str, total_steps: int, failed_steps: int) -> None:
        super().__init__(topic="WorkflowCompleted", data={
            "workflow_id": workflow_id, "total_steps": total_steps,
            "failed_steps": failed_steps
        })

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]

    @property
    def total_steps(self) -> int:
        return self.data["total_steps"]

    @property
    def failed_steps(self) -> int:
        return self.data["failed_steps"]


class WorkflowCancelled(OrionEvent):
    def __init__(self, workflow_id: str) -> None:
        super().__init__(topic="WorkflowCancelled", data={"workflow_id": workflow_id})

    @property
    def workflow_id(self) -> str:
        return self.data["workflow_id"]
