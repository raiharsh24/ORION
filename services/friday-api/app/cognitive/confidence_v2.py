from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class AgentConfidenceScore:
    agent_id: str
    role: str
    historical_success_rate: float = 0.5
    task_complexity_factor: float = 1.0
    confidence: float = 0.5
    risk: float = 0.3


@dataclass
class StrategyConfidenceScore:
    strategy_name: str
    expected_success_rate: float = 0.5
    confidence: float = 0.5
    risk: float = 0.3
    expected_duration_ms: float = 1000.0


@dataclass
class ToolConfidenceScore:
    tool_name: str
    historical_success_rate: float = 0.5
    confidence: float = 0.5
    risk: float = 0.2
    latency_factor: float = 1.0


@dataclass
class PreExecutionScore:
    capability: str
    recommended_strategy: str
    strategy_confidence: float
    agent_scores: List[AgentConfidenceScore]
    tool_scores: List[ToolConfidenceScore]
    overall_confidence: float
    overall_risk: float
    warnings: List[str] = field(default_factory=list)


class ConfidenceEngineV2:
    def __init__(self,
                 confidence_engine: Any = None,
                 adaptive_learning: Any = None) -> None:
        self._ce = confidence_engine
        self._adaptive = adaptive_learning
        self._evaluations: List[PreExecutionScore] = []

    def score_pre_execution(self, capability: str,
                            candidate_agents: List[Dict[str, Any]],
                            candidate_tools: List[str],
                            strategy: str = "direct") -> PreExecutionScore:
        agent_scores = self._score_agents(candidate_agents)
        tool_scores = self._score_tools(candidate_tools)
        strategy_score = self._score_strategy(strategy, capability)

        overall_conf = strategy_score.confidence * 0.4
        if agent_scores:
            overall_conf += (
                sum(a.confidence for a in agent_scores) / len(agent_scores)
            ) * 0.35
        if tool_scores:
            overall_conf += (
                sum(t.confidence for t in tool_scores) / len(tool_scores)
            ) * 0.25

        overall_risk = strategy_score.risk * 0.3
        if agent_scores:
            overall_risk += (
                sum(a.risk for a in agent_scores) / len(agent_scores)
            ) * 0.4
        if tool_scores:
            overall_risk += (
                sum(t.risk for t in tool_scores) / len(tool_scores)
            ) * 0.3

        warnings = self._generate_warnings(agent_scores, tool_scores, strategy_score)

        score = PreExecutionScore(
            capability=capability,
            recommended_strategy=strategy,
            strategy_confidence=strategy_score.confidence,
            agent_scores=agent_scores,
            tool_scores=tool_scores,
            overall_confidence=round(overall_conf, 4),
            overall_risk=round(overall_risk, 4),
            warnings=warnings,
        )
        self._evaluations.append(score)
        return score

    def _score_agents(self,
                      agents: List[Dict[str, Any]]) -> List[AgentConfidenceScore]:
        scores = []
        for agent in agents:
            agent_id = agent.get("agent_id", "unknown")
            role = agent.get("role", "unknown")
            historical_rate = 0.5
            if self._adaptive:
                historical_rate = self._adaptive.get_agent_reliability(
                    agent_id
                ).get("success_rate", 0.5)
            task_complexity = 1.0 - (agent.get("priority", 5) / 10.0) * 0.3
            confidence = historical_rate * task_complexity
            risk = 1.0 - confidence
            scores.append(AgentConfidenceScore(
                agent_id=agent_id,
                role=role,
                historical_success_rate=historical_rate,
                task_complexity_factor=round(task_complexity, 2),
                confidence=round(confidence, 4),
                risk=round(risk, 4),
            ))
        return scores

    def _score_tools(self, tools: List[str]) -> List[ToolConfidenceScore]:
        scores = []
        for tool_name in tools:
            historical_rate = 0.5
            if self._adaptive:
                historical_rate = self._adaptive.get_tool_success_rate(tool_name)
            latency_factor = 1.0
            if self._ce:
                step_score = self._ce.evaluate_step_by_action(tool_name)
                latency_factor = min(2.0, step_score.expected_duration_ms / 1000.0)
            confidence = historical_rate * (1.0 / max(latency_factor, 0.5))
            risk = 1.0 - confidence
            scores.append(ToolConfidenceScore(
                tool_name=tool_name,
                historical_success_rate=historical_rate,
                confidence=round(confidence, 4),
                risk=round(risk, 4),
                latency_factor=round(latency_factor, 2),
            ))
        return scores

    def _score_strategy(self, strategy: str,
                        capability: str) -> StrategyConfidenceScore:
        expected_rate = 0.5
        if self._adaptive:
            recs = self._adaptive.get_recommendations(capability)
            for rec in recs:
                if rec.recommended_strategy == strategy:
                    expected_rate = rec.expected_success_rate
                    break
        confidence = expected_rate + 0.1
        risk = 1.0 - confidence
        return StrategyConfidenceScore(
            strategy_name=strategy,
            expected_success_rate=expected_rate,
            confidence=round(min(confidence, 1.0), 4),
            risk=round(max(risk, 0.0), 4),
        )

    def _generate_warnings(self, agents: List[AgentConfidenceScore],
                           tools: List[ToolConfidenceScore],
                           strategy: StrategyConfidenceScore) -> List[str]:
        warnings = []
        for a in agents:
            if a.confidence < 0.3:
                warnings.append(f"Low confidence in agent '{a.agent_id}' ({a.confidence:.2f})")
        for t in tools:
            if t.confidence < 0.3:
                warnings.append(f"Low confidence in tool '{t.tool_name}' ({t.confidence:.2f})")
        if strategy.confidence < 0.3:
            warnings.append(f"Low confidence in strategy '{strategy.strategy_name}' ({strategy.confidence:.2f})")
        return warnings

    def should_proceed(self, score: PreExecutionScore,
                       min_confidence: float = 0.4,
                       max_risk: float = 0.6) -> bool:
        if score.overall_confidence < min_confidence:
            return False
        if score.overall_risk > max_risk:
            return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        if not self._evaluations:
            return {"total_evaluations": 0}
        avg_conf = sum(e.overall_confidence for e in self._evaluations) / len(self._evaluations)
        avg_risk = sum(e.overall_risk for e in self._evaluations) / len(self._evaluations)
        return {
            "total_evaluations": len(self._evaluations),
            "avg_overall_confidence": round(avg_conf, 4),
            "avg_overall_risk": round(avg_risk, 4),
        }
