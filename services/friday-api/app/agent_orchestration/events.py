from app.events.events import FridayEvent


class AgentMissionDelegated(FridayEvent):
    def __init__(self, mission_id: str, goal_plan_id: str,
                 agent_id: str, capability: str) -> None:
        super().__init__("agent.mission.delegated", {
            "mission_id": mission_id,
            "goal_plan_id": goal_plan_id,
            "agent_id": agent_id,
            "capability": capability,
        })


class AgentMissionCompleted(FridayEvent):
    def __init__(self, mission_id: str, agent_id: str,
                 success: bool, result: str = "") -> None:
        super().__init__("agent.mission.completed", {
            "mission_id": mission_id,
            "agent_id": agent_id,
            "success": success,
            "result": result,
        })


class AgentMissionFailed(FridayEvent):
    def __init__(self, mission_id: str, agent_id: str,
                 error: str) -> None:
        super().__init__("agent.mission.failed", {
            "mission_id": mission_id,
            "agent_id": agent_id,
            "error": error,
        })


class AgentAssistanceRequested(FridayEvent):
    def __init__(self, agent_id: str, mission_id: str,
                 capability_needed: str, context: str = "") -> None:
        super().__init__("agent.assistance.requested", {
            "agent_id": agent_id,
            "mission_id": mission_id,
            "capability_needed": capability_needed,
            "context": context,
        })


class AgentFindingsPublished(FridayEvent):
    def __init__(self, agent_id: str, mission_id: str,
                 findings: str, topic: str = "") -> None:
        super().__init__("agent.findings.published", {
            "agent_id": agent_id,
            "mission_id": mission_id,
            "findings": findings,
            "topic": topic,
        })


class HumanApprovalRequested(FridayEvent):
    def __init__(self, mission_id: str, objective: str,
                 agent_ids: list, estimated_duration_ms: float = 0.0) -> None:
        super().__init__("human.approval.requested", {
            "mission_id": mission_id,
            "objective": objective,
            "agent_ids": agent_ids,
            "estimated_duration_ms": estimated_duration_ms,
        })


class HumanApprovalGranted(FridayEvent):
    def __init__(self, mission_id: str, approved_by: str = "user") -> None:
        super().__init__("human.approval.granted", {
            "mission_id": mission_id,
            "approved_by": approved_by,
        })


class HumanApprovalDenied(FridayEvent):
    def __init__(self, mission_id: str, reason: str = "") -> None:
        super().__init__("human.approval.denied", {
            "mission_id": mission_id,
            "reason": reason,
        })
