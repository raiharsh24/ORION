import math
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger

from app.planning.base import Plan, PlanStep


@dataclass
class ConfidenceScore:
    confidence: float = 1.0
    risk: float = 0.0
    expected_duration_ms: float = 0.0
    has_fallback: bool = False
    fallback_type: str = ""
    factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class StepConfidence:
    step_id: str
    action_name: str
    confidence: float = 1.0
    risk: float = 0.0
    expected_duration_ms: float = 0.0
    has_fallback: bool = False
    fallback_type: str = ""


@dataclass
class PlanConfidence:
    plan_id: str
    steps: List[StepConfidence] = field(default_factory=list)
    overall_confidence: float = 1.0
    overall_risk: float = 0.0
    total_expected_duration_ms: float = 0.0
    high_risk_steps: int = 0
    steps_with_fallback: int = 0


class ConfidenceEngine:
    """Scores every plan step with confidence, risk, expected duration,
    and fallback availability. Scores influence planning decisions.

    Reuses existing SimulationEngine and HeuristicScorer infrastructure
    for consistency.
    """

    # Base confidence by action type
    ACTION_CONFIDENCE = {
        "filesystem": 0.95,
        "knowledge.search": 0.90,
        "browser": 0.80,
        "terminal": 0.75,
        "open_app": 0.85,
        "clipboard": 0.95,
        "desktop.notifications": 0.95,
        "desktop.screenshot": 0.90,
        "plan": 0.85,
        "research": 0.80,
        "analyze": 0.85,
        "code": 0.75,
        "test": 0.80,
        "deploy": 0.70,
    }

    # Risk by action type
    ACTION_RISK = {
        "terminal": 0.30,
        "deploy": 0.35,
        "code": 0.20,
        "test": 0.15,
        "browser": 0.10,
        "filesystem": 0.15,
        "open_app": 0.05,
        "clipboard": 0.05,
        "knowledge.search": 0.05,
        "desktop.screenshot": 0.05,
        "desktop.notifications": 0.05,
        "plan": 0.05,
        "research": 0.10,
        "analyze": 0.05,
    }

    # Fallback availability by action type
    ACTION_FALLBACK = {
        "terminal": "alternative_tool",
        "browser": "alternative_tool",
        "filesystem": "retry",
        "code": "retry",
        "deploy": "alternative_workflow",
        "knowledge.search": "alternative_tool",
        "open_app": "ask_user",
        "test": "retry",
    }

    def __init__(self) -> None:
        self._scores: Dict[str, PlanConfidence] = {}
        self._evaluation_count = 0

    def evaluate_step(self, step: PlanStep) -> ConfidenceScore:
        action_key = step.action_id
        base_conf = self.ACTION_CONFIDENCE.get(action_key, 0.80)
        base_risk = self.ACTION_RISK.get(action_key, 0.15)
        has_fallback = step.fallback_step_id is not None or action_key in self.ACTION_FALLBACK
        fallback_type = self.ACTION_FALLBACK.get(action_key, "")

        factors: Dict[str, float] = {
            "base_confidence": base_conf,
            "base_risk": base_risk,
            "complexity_penalty": 0.0,
            "dependency_penalty": 0.0,
        }

        if len(step.dependencies) > 2:
            dep_penalty = (len(step.dependencies) - 2) * 0.05
            factors["dependency_penalty"] = dep_penalty
            base_conf = max(0.1, base_conf - dep_penalty)

        estimated = step.estimated_duration * 1000

        return ConfidenceScore(
            confidence=round(base_conf, 4),
            risk=round(base_risk, 4),
            expected_duration_ms=estimated,
            has_fallback=has_fallback,
            fallback_type=fallback_type,
            factors=factors,
        )

    def evaluate_step_by_action(self, action_id: str, duration_ms: float = 1000.0) -> ConfidenceScore:
        base_conf = self.ACTION_CONFIDENCE.get(action_id, 0.80)
        base_risk = self.ACTION_RISK.get(action_id, 0.15)
        has_fallback = action_id in self.ACTION_FALLBACK
        fallback_type = self.ACTION_FALLBACK.get(action_id, "")

        return ConfidenceScore(
            confidence=round(base_conf, 4),
            risk=round(base_risk, 4),
            expected_duration_ms=duration_ms,
            has_fallback=has_fallback,
            fallback_type=fallback_type,
            factors={"base_confidence": base_conf, "base_risk": base_risk},
        )

    def evaluate_plan(self, plan: Plan) -> PlanConfidence:
        self._evaluation_count += 1
        step_scores: List[StepConfidence] = []
        high_risk = 0
        with_fallback = 0
        total_duration = 0.0

        for step in plan.steps:
            score = self.evaluate_step(step)
            step_conf = StepConfidence(
                step_id=step.step_id,
                action_name=step.action_name,
                confidence=score.confidence,
                risk=score.risk,
                expected_duration_ms=score.expected_duration_ms,
                has_fallback=score.has_fallback,
                fallback_type=score.fallback_type,
            )
            step_scores.append(step_conf)
            total_duration += score.expected_duration_ms
            if score.risk > 0.25:
                high_risk += 1
            if score.has_fallback:
                with_fallback += 1

        overall_conf = (
            sum(s.confidence for s in step_scores) / len(step_scores)
            if step_scores else 1.0
        )
        overall_risk = (
            sum(s.risk for s in step_scores) / len(step_scores)
            if step_scores else 0.0
        )

        plan_conf = PlanConfidence(
            plan_id=plan.plan_id,
            steps=step_scores,
            overall_confidence=round(overall_conf, 4),
            overall_risk=round(overall_risk, 4),
            total_expected_duration_ms=round(total_duration, 2),
            high_risk_steps=high_risk,
            steps_with_fallback=with_fallback,
        )
        self._scores[plan.plan_id] = plan_conf
        return plan_conf

    def get_plan_confidence(self, plan_id: str) -> Optional[PlanConfidence]:
        return self._scores.get(plan_id)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "evaluations": self._evaluation_count,
            "cached_scores": len(self._scores),
        }
