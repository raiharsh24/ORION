import asyncio
import time
from typing import Dict, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from loguru import logger

from app.events.events import FridayEvent
from app.events.bus import EventBus
from app.agent_orchestration.events import (
    HumanApprovalRequested, HumanApprovalGranted, HumanApprovalDenied,
)


@dataclass
class ApprovalRequest:
    mission_id: str
    objective: str
    agent_ids: list
    estimated_duration_ms: float = 0.0
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    approved_by: str = ""
    reason: str = ""


class HumanOversightManager:
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self._event_bus = event_bus
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._auto_approve_threshold_ms: float = 30000.0
        self._pending_approval_events: Dict[str, asyncio.Event] = {}
        self._approval_count = 0
        self._denial_count = 0
        self._interrupted_missions: Set[str] = set()

    @property
    def auto_approve_threshold_ms(self) -> float:
        return self._auto_approve_threshold_ms

    @auto_approve_threshold_ms.setter
    def auto_approve_threshold_ms(self, value: float) -> None:
        self._auto_approve_threshold_ms = value

    async def request_approval(
        self,
        mission_id: str,
        objective: str,
        agent_ids: list,
        estimated_duration_ms: float = 0.0,
        wait: bool = True,
        timeout: float = 300.0,
    ) -> bool:
        if estimated_duration_ms <= self._auto_approve_threshold_ms:
            logger.info(
                f"HumanOversight: Auto-approved '{objective[:60]}' "
                f"({estimated_duration_ms:.0f}ms <= {self._auto_approve_threshold_ms:.0f}ms)"
            )
            self._approval_count += 1
            return True

        request = ApprovalRequest(
            mission_id=mission_id,
            objective=objective,
            agent_ids=agent_ids,
            estimated_duration_ms=estimated_duration_ms,
        )
        self._pending_approvals[mission_id] = request

        self._publish(HumanApprovalRequested(
            mission_id=mission_id,
            objective=objective,
            agent_ids=agent_ids,
            estimated_duration_ms=estimated_duration_ms,
        ))

        if not wait:
            return False

        event = asyncio.Event()
        self._pending_approval_events[mission_id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"HumanOversight: Approval timeout for mission '{mission_id}'"
            )
            request.status = "timed_out"
            self._pending_approvals.pop(mission_id, None)
            self._pending_approval_events.pop(mission_id, None)
            return False

        request = self._pending_approvals.pop(mission_id, None)
        self._pending_approval_events.pop(mission_id, None)
        if request and request.status == "approved":
            return True
        return False

    async def approve(self, mission_id: str, approved_by: str = "user") -> bool:
        request = self._pending_approvals.get(mission_id)
        if not request:
            return False
        request.status = "approved"
        request.resolved_at = time.time()
        request.approved_by = approved_by
        self._approval_count += 1
        self._publish(HumanApprovalGranted(mission_id=mission_id, approved_by=approved_by))
        event = self._pending_approval_events.get(mission_id)
        if event:
            event.set()
        return True

    async def deny(self, mission_id: str, reason: str = "") -> bool:
        request = self._pending_approvals.get(mission_id)
        if not request:
            return False
        request.status = "denied"
        request.resolved_at = time.time()
        request.reason = reason
        self._denial_count += 1
        self._publish(HumanApprovalDenied(mission_id=mission_id, reason=reason))
        event = self._pending_approval_events.get(mission_id)
        if event:
            event.set()
        return True

    def has_pending(self, mission_id: str) -> bool:
        return mission_id in self._pending_approvals

    def list_pending(self) -> list:
        return [
            {
                "mission_id": r.mission_id,
                "objective": r.objective[:100],
                "agent_ids": r.agent_ids,
                "estimated_duration_ms": r.estimated_duration_ms,
                "created_at": r.created_at,
            }
            for r in self._pending_approvals.values()
        ]

    def interrupt_mission(self, mission_id: str) -> None:
        self._interrupted_missions.add(mission_id)

    def resume_mission(self, mission_id: str) -> None:
        self._interrupted_missions.discard(mission_id)

    def is_interrupted(self, mission_id: str) -> bool:
        return mission_id in self._interrupted_missions

    def get_stats(self) -> Dict[str, Any]:
        return {
            "pending_approvals": len(self._pending_approvals),
            "total_approved": self._approval_count,
            "total_denied": self._denial_count,
            "interrupted_missions": list(self._interrupted_missions),
            "auto_approve_threshold_ms": self._auto_approve_threshold_ms,
        }

    def _publish(self, event: FridayEvent) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
