import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ExecutionQuality:
    stage_success_rate: float = 1.0
    recovery_effectiveness: float = 1.0
    avg_stage_duration_ms: float = 0.0
    total_retries: int = 0
    total_recoveries: int = 0
    unexpected_errors: int = 0


@dataclass
class FailureRecord:
    stage: str
    error: str
    category: str = "unknown"
    recovery_used: str = ""
    recovery_success: bool = False
    duration_ms: float = 0.0


@dataclass
class SuccessStrategy:
    description: str
    category: str = "general"
    effectiveness_score: float = 1.0
    times_used: int = 1


@dataclass
class ReflectionV2Report:
    mission_id: str
    goal_id: str = ""
    execution_quality: ExecutionQuality = field(default_factory=ExecutionQuality)
    failures: List[FailureRecord] = field(default_factory=list)
    success_strategies: List[SuccessStrategy] = field(default_factory=list)
    planner_accuracy: float = 1.0
    tool_effectiveness: Dict[str, float] = field(default_factory=dict)
    agent_performance: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    reflection_id: str = ""


class ReflectionV2:
    def __init__(self, learning_engine: Any = None,
                 reflection_engine: Any = None,
                 goal_memory: Any = None,
                 adaptive_learning: Any = None) -> None:
        self._learning = learning_engine
        self._reflection_engine = reflection_engine
        self._goal_memory = goal_memory
        self._adaptive_learning = adaptive_learning
        self._reports: List[ReflectionV2Report] = []

    async def analyze(self, mission_id: str, goal_id: str = "",
                      execution_data: Optional[Dict[str, Any]] = None,
                      existing_report: Any = None) -> ReflectionV2Report:
        report = ReflectionV2Report(
            reflection_id=str(uuid.uuid4()),
            mission_id=mission_id,
            goal_id=goal_id,
        )

        if existing_report:
            self._extract_from_existing(report, existing_report)

        if execution_data:
            self._analyze_execution_data(report, execution_data)

        self._assess_planner_accuracy(report)
        self._assess_tool_effectiveness(report)
        self._assess_agent_performance(report)
        self._generate_recommendations(report)

        self._store_reflection(report)
        self._update_goal_progress(report)

        self._reports.append(report)
        return report

    def _extract_from_existing(self, report: ReflectionV2Report,
                                existing: Any) -> None:
        if hasattr(existing, 'what_succeeded'):
            for s in existing.what_succeeded:
                report.success_strategies.append(SuccessStrategy(
                    description=s, category="success",
                ))
        if hasattr(existing, 'what_failed'):
            for f in existing.what_failed:
                report.failures.append(FailureRecord(
                    stage="unknown", error=f, category="failure",
                ))
        if hasattr(existing, 'planner_accuracy'):
            report.planner_accuracy = existing.planner_accuracy
        if hasattr(existing, 'recommended_improvements'):
            report.recommendations = existing.recommended_improvements

        quality = report.execution_quality
        quality.stage_success_rate = existing.planner_accuracy if hasattr(existing, 'planner_accuracy') else 1.0
        if hasattr(existing, 'lessons'):
            for lesson in existing.lessons:
                if lesson.category == "reliability" and "retries" in lesson.description.lower():
                    quality.total_retries += 1
                if lesson.category == "recovery":
                    quality.total_recoveries += 1

    def _analyze_execution_data(self, report: ReflectionV2Report,
                                 data: Dict[str, Any]) -> None:
        quality = report.execution_quality
        stages = data.get("stages", [])
        if stages:
            completed = sum(1 for s in stages if s.get("status") == "completed")
            quality.stage_success_rate = round(completed / len(stages), 3) if stages else 1.0
            durations = [s.get("duration_ms", 0) for s in stages if s.get("duration_ms")]
            quality.avg_stage_duration_ms = round(
                sum(durations) / len(durations), 1
            ) if durations else 0.0

        quality.total_retries = data.get("retry_count", 0)
        quality.total_recoveries = data.get("recovery_count", 0)
        quality.unexpected_errors = len(data.get("errors", []))

        for f_data in data.get("failures", []):
            report.failures.append(FailureRecord(
                stage=f_data.get("stage", "unknown"),
                error=f_data.get("error", "unknown"),
                category=f_data.get("category", "unknown"),
                recovery_used=f_data.get("recovery", ""),
                recovery_success=f_data.get("recovery_success", False),
                duration_ms=f_data.get("duration_ms", 0),
            ))

        for s_data in data.get("successes", []):
            report.success_strategies.append(SuccessStrategy(
                description=s_data.get("description", "Success"),
                category=s_data.get("category", "general"),
                effectiveness_score=s_data.get("effectiveness", 1.0),
            ))

    def _assess_planner_accuracy(self, report: ReflectionV2Report) -> None:
        if not self._learning:
            return
        try:
            learnings = self._learning.get_relevant_learnings(
                learning_type="mission_outcome", limit=50
            )
            correct = sum(1 for e in learnings if e.metadata.get("success"))
            total = len(learnings)
            if total > 0:
                report.planner_accuracy = round(correct / total, 3)
        except Exception:
            pass

    def _assess_tool_effectiveness(self, report: ReflectionV2Report) -> None:
        if not self._learning:
            return
        try:
            tool_stats = self._learning.get_tool_effectiveness()
            report.tool_effectiveness = {
                tool: stats["success_rate"] for tool, stats in tool_stats.items()
            }
        except Exception:
            pass

    def _assess_agent_performance(self, report: ReflectionV2Report) -> None:
        if not self._learning:
            return
        try:
            learnings = self._learning.get_relevant_learnings(
                learning_type="mission_outcome", limit=100
            )
            agent_data: Dict[str, List[bool]] = {}
            for entry in learnings:
                meta = entry.metadata
                agent = meta.get("agent_id", meta.get("delegated_agent", ""))
                if not agent:
                    continue
                if agent not in agent_data:
                    agent_data[agent] = []
                agent_data[agent].append(meta.get("success", False))
            report.agent_performance = {
                agent: round(sum(results) / len(results), 3)
                for agent, results in agent_data.items()
            }
        except Exception:
            pass

    def _generate_recommendations(self, report: ReflectionV2Report) -> None:
        recs = []

        if report.execution_quality.stage_success_rate < 0.8:
            recs.append(
                f"Improve stage reliability "
                f"(current: {report.execution_quality.stage_success_rate:.0%})"
            )

        if report.execution_quality.total_recoveries > 3:
            recs.append(
                f"Review recovery strategies "
                f"({report.execution_quality.total_recoveries} recoveries)"
            )

        if report.failures:
            top_failures = report.failures[:3]
            for f in top_failures:
                recs.append(
                    f"Address failure in '{f.stage}': {f.error[:80]}"
                )

        for tool, rate in report.tool_effectiveness.items():
            if rate < 0.5:
                recs.append(f"Consider replacing or fixing tool '{tool}' ({rate:.0%})")

        for agent, rate in report.agent_performance.items():
            if rate < 0.5:
                recs.append(f"Review agent '{agent}' performance ({rate:.0%})")

        if report.success_strategies:
            best = max(report.success_strategies,
                       key=lambda s: s.effectiveness_score)
            recs.append(
                f"Replicate strategy: {best.description[:80]}"
            )

        if not recs:
            recs.append("Maintain current patterns")

        report.recommendations = recs

    def _store_reflection(self, report: ReflectionV2Report) -> None:
        if not self._learning:
            return
        try:
            summary = (
                f"ReflectionV2 {report.mission_id[:8]}: "
                f"quality={report.execution_quality.stage_success_rate:.0%}, "
                f"failures={len(report.failures)}, "
                f"strategies={len(report.success_strategies)}"
            )
            self._learning.record_reflection(
                category="reflection_v2",
                description=summary,
                severity="info",
                recommendation="; ".join(report.recommendations[:3]),
                mission_id=report.mission_id,
            )
            if self._adaptive_learning:
                self._adaptive_learning.refresh_from_history()
        except Exception:
            pass

    def _update_goal_progress(self, report: ReflectionV2Report) -> None:
        if not self._goal_memory or not report.goal_id:
            return
        try:
            goal = self._goal_memory.get_goal(report.goal_id)
            if goal:
                quality = report.execution_quality
                progress_delta = quality.stage_success_rate * 100.0 * 0.1
                new_progress = min(100.0, goal.progress_pct + progress_delta)
                self._goal_memory.update_goal(
                    report.goal_id,
                    progress_pct=round(new_progress, 1),
                )
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        if not self._reports:
            return {"total_reflections": 0}
        avg_quality = sum(
            r.execution_quality.stage_success_rate for r in self._reports
        ) / len(self._reports)
        total_failures = sum(len(r.failures) for r in self._reports)
        total_strategies = sum(len(r.success_strategies) for r in self._reports)
        return {
            "total_reflections": len(self._reports),
            "avg_stage_success_rate": round(avg_quality, 3),
            "total_failures_recorded": total_failures,
            "total_strategies_recorded": total_strategies,
        }
