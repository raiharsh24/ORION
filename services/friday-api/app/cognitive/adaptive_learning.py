import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class StrategyScore:
    strategy_name: str
    success_count: int = 0
    fail_count: int = 0
    total_duration_ms: float = 0.0
    avg_confidence: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return round(self.success_count / total, 3) if total > 0 else 0.0


@dataclass
class PlannerRecommendation:
    capability: str
    recommended_strategy: str
    confidence: float
    expected_success_rate: float
    based_on_samples: int
    alternative_strategies: List[str] = field(default_factory=list)


class AdaptiveLearning:
    def __init__(self, learning_engine: Any = None,
                 goal_memory: Any = None) -> None:
        self._learning = learning_engine
        self._goal_memory = goal_memory
        self._strategy_scores: Dict[str, StrategyScore] = {}
        self._agent_reliability: Dict[str, Dict[str, Any]] = {}
        self._tool_success_rates: Dict[str, float] = {}
        self._learning_rounds = 0

    def refresh_from_history(self) -> None:
        self._refresh_strategy_scores()
        self._refresh_agent_reliability()
        self._refresh_tool_rates()
        self._learning_rounds += 1

    def _refresh_strategy_scores(self) -> None:
        if not self._learning:
            return
        strategies = {
            "direct": {"success": 0, "fail": 0, "duration": 0.0, "confidence": 0.0},
            "delegated": {"success": 0, "fail": 0, "duration": 0.0, "confidence": 0.0},
            "recovery": {"success": 0, "fail": 0, "duration": 0.0, "confidence": 0.0},
            "parallel": {"success": 0, "fail": 0, "duration": 0.0, "confidence": 0.0},
        }
        try:
            learnings = self._learning.get_relevant_learnings(
                learning_type="mission_outcome", limit=100
            )
            for entry in learnings:
                meta = entry.metadata
                strat = meta.get("strategy", "direct")
                if strat not in strategies:
                    strat = "direct"
                success = meta.get("success", False)
                if success:
                    strategies[strat]["success"] += 1
                else:
                    strategies[strat]["fail"] += 1
                strategies[strat]["duration"] += meta.get("duration_ms", 0)
                strategies[strat]["confidence"] += meta.get("confidence", 0.5)

            for strat_name, data in strategies.items():
                total = data["success"] + data["fail"]
                avg_conf = data["confidence"] / total if total > 0 else 0.5
                self._strategy_scores[strat_name] = StrategyScore(
                    strategy_name=strat_name,
                    success_count=data["success"],
                    fail_count=data["fail"],
                    total_duration_ms=data["duration"],
                    avg_confidence=round(avg_conf, 3),
                )
        except Exception:
            pass

    def _refresh_agent_reliability(self) -> None:
        if not self._learning:
            return
        try:
            learnings = self._learning.get_relevant_learnings(
                learning_type="mission_outcome", limit=200
            )
            agent_data: Dict[str, Dict[str, Any]] = {}
            for entry in learnings:
                meta = entry.metadata
                agent = meta.get("agent_id", meta.get("delegated_agent", "unknown"))
                if agent == "unknown":
                    continue
                if agent not in agent_data:
                    agent_data[agent] = {"success": 0, "fail": 0, "total_duration": 0.0, "count": 0}
                if meta.get("success"):
                    agent_data[agent]["success"] += 1
                else:
                    agent_data[agent]["fail"] += 1
                agent_data[agent]["total_duration"] += meta.get("duration_ms", 0)
                agent_data[agent]["count"] += 1

            self._agent_reliability = {}
            for agent_id, data in agent_data.items():
                total = data["success"] + data["fail"]
                self._agent_reliability[agent_id] = {
                    "success_rate": round(data["success"] / total, 3) if total > 0 else 0.5,
                    "total_tasks": total,
                    "avg_duration_ms": round(data["total_duration"] / total, 1) if total > 0 else 0.0,
                }
        except Exception:
            pass

    def _refresh_tool_rates(self) -> None:
        if not self._learning:
            return
        try:
            tool_stats = self._learning.get_tool_effectiveness()
            self._tool_success_rates = {
                tool: stats["success_rate"]
                for tool, stats in tool_stats.items()
            }
        except Exception:
            pass

    def get_recommendations(self, capability: str) -> List[PlannerRecommendation]:
        self.refresh_from_history()
        recommendations = []

        strategy_map = {
            "task_decomposition": ["direct", "delegated"],
            "web_search": ["direct", "delegated"],
            "code_generation": ["direct", "delegated", "parallel"],
            "code_review": ["delegated", "direct"],
            "tool_execution": ["direct", "recovery"],
            "information_synthesis": ["direct", "delegated"],
        }

        candidates = strategy_map.get(capability, ["direct"])
        scored = []
        for strat in candidates:
            score = self._strategy_scores.get(strat, StrategyScore(strategy_name=strat))
            total = score.success_count + score.fail_count
            if total > 0:
                scored.append((strat, score.success_rate, total))
        scored.sort(key=lambda x: (-x[1], -x[2]))

        if scored:
            best = scored[0]
            alternatives = [s[0] for s in scored[1:]]
            recommendations.append(PlannerRecommendation(
                capability=capability,
                recommended_strategy=best[0],
                confidence=round(best[1], 2),
                expected_success_rate=round(best[1], 2),
                based_on_samples=best[2],
                alternative_strategies=alternatives,
            ))
        else:
            recommendations.append(PlannerRecommendation(
                capability=capability,
                recommended_strategy="direct",
                confidence=0.5,
                expected_success_rate=0.5,
                based_on_samples=0,
                alternative_strategies=[],
            ))
        return recommendations

    def get_agent_reliability(self, agent_id: str) -> Dict[str, Any]:
        self.refresh_from_history()
        return self._agent_reliability.get(agent_id, {
            "success_rate": 0.5, "total_tasks": 0, "avg_duration_ms": 0.0,
        })

    def get_tool_success_rate(self, tool_name: str) -> float:
        self.refresh_from_history()
        return self._tool_success_rates.get(tool_name, 0.5)

    def get_best_strategy(self, capability: str) -> str:
        recs = self.get_recommendations(capability)
        if recs:
            return recs[0].recommended_strategy
        return "direct"

    def get_summary(self) -> Dict[str, Any]:
        self.refresh_from_history()
        return {
            "learning_rounds": self._learning_rounds,
            "strategies": {
                name: {
                    "success_rate": s.success_rate,
                    "total": s.success_count + s.fail_count,
                    "avg_confidence": s.avg_confidence,
                }
                for name, s in self._strategy_scores.items()
                if s.success_count + s.fail_count > 0
            },
            "agents_tracked": len(self._agent_reliability),
            "tools_tracked": len(self._tool_success_rates),
        }
