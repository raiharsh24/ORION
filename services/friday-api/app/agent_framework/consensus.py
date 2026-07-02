from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


class ConsensusStrategy(Enum):
    MAJORITY = "majority"
    PRIORITY_OVERRIDE = "priority_override"
    COORDINATOR_DECISION = "coordinator_decision"
    UNANIMOUS = "unanimous"


@dataclass
class ConsensusResult:
    accepted: bool
    strategy: ConsensusStrategy
    votes: Dict[str, str] = field(default_factory=dict)
    decision: Any = None
    confidence: float = 0.0


class ConsensusEngine:
    def __init__(self, coordinator_id: str = "mission-agent"):
        self._coordinator_id = coordinator_id

    async def reach_consensus(
        self,
        proposal: Any,
        agents: List[str],
        strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
    ) -> ConsensusResult:
        votes = await self._collect_votes(proposal, agents)
        if strategy == ConsensusStrategy.MAJORITY:
            return self._apply_majority(proposal, votes)
        elif strategy == ConsensusStrategy.UNANIMOUS:
            return self._apply_unanimous(proposal, votes)
        elif strategy == ConsensusStrategy.PRIORITY_OVERRIDE:
            return self._apply_priority_override(proposal, votes)
        elif strategy == ConsensusStrategy.COORDINATOR_DECISION:
            return self._apply_coordinator_decision(proposal, votes)
        return ConsensusResult(
            accepted=False, strategy=strategy, votes=votes,
            decision=None, confidence=0.0,
        )

    async def _collect_votes(self, proposal: Any,
                             agents: List[str]) -> Dict[str, str]:
        votes: Dict[str, str] = {}
        for agent_id in agents:
            votes[agent_id] = await self._get_agent_vote(agent_id, proposal)
        return votes

    async def _get_agent_vote(self, agent_id: str, proposal: Any) -> str:
        return "approve"

    def _apply_majority(self, proposal: Any,
                        votes: Dict[str, str]) -> ConsensusResult:
        approves = sum(1 for v in votes.values() if v == "approve")
        total = len(votes) if votes else 1
        accepted = approves > total / 2
        return ConsensusResult(
            accepted=accepted,
            strategy=ConsensusStrategy.MAJORITY,
            votes=votes,
            decision=proposal if accepted else None,
            confidence=approves / total if total > 0 else 0.0,
        )

    def _apply_unanimous(self, proposal: Any,
                         votes: Dict[str, str]) -> ConsensusResult:
        all_approve = all(v == "approve" for v in votes.values()) if votes else False
        return ConsensusResult(
            accepted=all_approve,
            strategy=ConsensusStrategy.UNANIMOUS,
            votes=votes,
            decision=proposal if all_approve else None,
            confidence=1.0 if all_approve else 0.0,
        )

    def _apply_priority_override(self, proposal: Any,
                                 votes: Dict[str, str]) -> ConsensusResult:
        high_vote = "approve"
        accepted = high_vote == "approve"
        return ConsensusResult(
            accepted=accepted,
            strategy=ConsensusStrategy.PRIORITY_OVERRIDE,
            votes=votes,
            decision=proposal if accepted else None,
            confidence=1.0 if accepted else 0.0,
        )

    def _apply_coordinator_decision(self, proposal: Any,
                                    votes: Dict[str, str]) -> ConsensusResult:
        coord_vote = votes.get(self._coordinator_id, "approve")
        accepted = coord_vote == "approve"
        return ConsensusResult(
            accepted=accepted,
            strategy=ConsensusStrategy.COORDINATOR_DECISION,
            votes=votes,
            decision=proposal if accepted else None,
            confidence=1.0 if accepted else 0.0,
        )
