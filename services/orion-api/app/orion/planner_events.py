from app.events.events import OrionEvent
from typing import Dict, Any, List

class PlanCreated(OrionEvent):
    def __init__(self, plan_data: Dict[str, Any]) -> None:
        super().__init__(topic="PlanCreated", data={"plan": plan_data})

class PlanValidated(OrionEvent):
    def __init__(self, plan_data: Dict[str, Any]) -> None:
        super().__init__(topic="PlanValidated", data={"plan": plan_data})

class PlanRejected(OrionEvent):
    def __init__(self, reason: str, plan_data: Dict[str, Any]) -> None:
        super().__init__(topic="PlanRejected", data={"reason": reason, "plan": plan_data})

class ClarificationRequested(OrionEvent):
    def __init__(self, question: str, intent: str) -> None:
        super().__init__(topic="ClarificationRequested", data={"question": question, "intent": intent})

class IntentDetected(OrionEvent):
    def __init__(self, query: str, intent: str) -> None:
        super().__init__(topic="IntentDetected", data={"query": query, "intent": intent})

class CapabilityResolved(OrionEvent):
    def __init__(self, intent: str, capabilities: List[str]) -> None:
        super().__init__(topic="CapabilityResolved", data={"intent": intent, "capabilities": capabilities})

class PlannerError(OrionEvent):
    def __init__(self, message: str) -> None:
        super().__init__(topic="PlannerError", data={"message": message})
