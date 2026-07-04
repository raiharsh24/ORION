import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from app.runtime.base import Mission, ExecutionResult
from app.runtime.telemetry import MissionTelemetry


@dataclass
class Lesson:
    category: str
    description: str
    severity: str = "info"
    recommendation: str = ""


@dataclass
class ToolPerformance:
    tool_name: str
    success_count: int = 0
    fail_count: int = 0
    total_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return round(self.success_count / total, 2) if total > 0 else 0.0


@dataclass
class ReflectionReport:
    mission_id: str
    total_duration_ms: float = 0.0
    planned_duration_ms: float = 0.0
    actual_duration_ms: float = 0.0
    duration_variance: float = 0.0
    stages_planned: int = 0
    stages_completed: int = 0
    bottlenecks: List[str] = field(default_factory=list)
    lessons: List[Lesson] = field(default_factory=list)
    experience_id: Optional[str] = None
    what_succeeded: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    tool_performance: List[ToolPerformance] = field(default_factory=list)
    unexpected_events: List[str] = field(default_factory=list)
    planner_accuracy: float = 1.0
    recommended_improvements: List[str] = field(default_factory=list)


class ReflectionEngine:
    def __init__(self, plan_memory: Any = None,
                 learning_engine: Any = None):
        self._plan_memory = plan_memory
        self._learning_engine = learning_engine
        self._experience_count = 0

    async def reflect(self, mission: Mission,
                       execution_result: ExecutionResult,
                       telemetry: Optional[MissionTelemetry] = None
                       ) -> ReflectionReport:
        report = ReflectionReport(
            mission_id=mission.mission_id,
            total_duration_ms=mission.total_duration_ms,
            stages_planned=len(mission.stages),
            stages_completed=execution_result.stages_completed,
        )

        report.bottlenecks = self._find_bottlenecks(mission, telemetry)
        report.lessons = self._generate_lessons(mission, execution_result, telemetry)
        report.what_succeeded = self._find_successes(mission, execution_result)
        report.what_failed = self._find_failures(mission, execution_result)
        report.tool_performance = self._assess_tool_performance(mission, telemetry)
        report.unexpected_events = self._find_unexpected(mission, telemetry)
        report.planner_accuracy = self._assess_planner_accuracy(mission, execution_result)
        report.recommended_improvements = self._generate_recommendations(report)

        if execution_result.success:
            report.experience_id = await self._store_experience(
                mission, execution_result, report,
            )

        await self._store_learning(report)

        return report

    def _find_successes(self, mission: Mission,
                        result: ExecutionResult) -> List[str]:
        successes = []
        for stage in mission.stages:
            if stage.status == "completed":
                successes.append(f"Stage '{stage.name}' completed")
        if result.success:
            successes.append("Mission objectives achieved")
        return successes

    def _find_failures(self, mission: Mission,
                       result: ExecutionResult) -> List[str]:
        failures = []
        for stage in mission.stages:
            if stage.status == "failed":
                failures.append(
                    f"Stage '{stage.name}' failed: {stage.error or 'unknown'}"
                )
        if not result.success:
            failures.append(
                f"Mission failed: {result.error or 'execution error'}"
            )
        return failures

    def _assess_tool_performance(
        self, mission: Mission, telemetry: Optional[MissionTelemetry]
    ) -> List[ToolPerformance]:
        tool_map: Dict[str, ToolPerformance] = {}
        if telemetry:
            for tool_name, latency in telemetry.tool_latencies.items():
                if tool_name not in tool_map:
                    tool_map[tool_name] = ToolPerformance(tool_name=tool_name)
                tool_map[tool_name].total_duration_ms += latency
                tool_map[tool_name].success_count += 1

        if mission.metadata:
            tool_ids = mission.metadata.get("tool_ids", [])
            for tid in tool_ids:
                if tid not in tool_map:
                    tool_map[tid] = ToolPerformance(tool_name=tid)

        return list(tool_map.values())

    def _find_unexpected(self, mission: Mission,
                         telemetry: Optional[MissionTelemetry]) -> List[str]:
        events = []
        if mission.error:
            events.append(f"Unexpected error: {mission.error}")
        if telemetry:
            if telemetry.retry_count > 0:
                events.append(f"Required {telemetry.retry_count} retries")
            if telemetry.recovery_count > 0:
                events.append(f"Recovery triggered {telemetry.recovery_count} times")
        if mission.total_duration_ms > 300000:
            events.append(f"Mission duration exceeded 5 minutes")
        return events

    def _assess_planner_accuracy(self, mission: Mission,
                                 result: ExecutionResult) -> float:
        if not mission.stages:
            return 1.0
        completed = sum(1 for s in mission.stages if s.status == "completed")
        total = len(mission.stages)
        return round(completed / total, 2) if total > 0 else 1.0

    def _generate_recommendations(self, report: ReflectionReport) -> List[str]:
        recs = []

        if report.tool_performance:
            for tp in report.tool_performance:
                if tp.success_rate < 0.5 and tp.fail_count > 0:
                    recs.append(
                        f"Consider replacing '{tp.tool_name}' "
                        f"(success rate: {tp.success_rate})"
                    )

        if report.bottlenecks:
            recs.append(
                f"Address bottlenecks: {'; '.join(report.bottlenecks[:2])}"
            )

        if report.total_duration_ms > 120000:
            recs.append(
                f"Optimize for shorter execution "
                f"(current: {report.total_duration_ms:.0f}ms)"
            )

        if report.planner_accuracy < 0.8:
            recs.append(
                f"Improve planner accuracy "
                f"(current: {report.planner_accuracy:.0%})"
            )

        if not recs:
            recs.append("Continue current patterns")

        return recs

    def _find_bottlenecks(self, mission: Mission,
                           telemetry: Optional[MissionTelemetry]
                           ) -> List[str]:
        bottlenecks: List[str] = []

        if telemetry:
            stage_timings = telemetry.stage_timings
            if stage_timings:
                max_stage = max(stage_timings, key=stage_timings.get)
                bottlenecks.append(
                    f"Stage '{max_stage}' took {stage_timings[max_stage]:.1f}ms"
                )

        slow_stages = [s for s in mission.stages
                       if s.status == "completed" and s.duration_ms > 1000]
        for s in slow_stages:
            bottlenecks.append(
                f"Stage '{s.name}' took {s.duration_ms:.1f}ms"
            )

        return bottlenecks

    def _generate_lessons(self, mission: Mission,
                           result: ExecutionResult,
                           telemetry: Optional[MissionTelemetry]
                           ) -> List[Lesson]:
        lessons: List[Lesson] = []

        if result.success:
            lessons.append(Lesson(
                category="success",
                description=f"Mission {mission.mission_id} completed successfully",
                severity="info",
                recommendation="Consider this mission pattern for similar requests",
            ))
        else:
            lessons.append(Lesson(
                category="failure",
                description=f"Mission failed: {result.error}",
                severity="error",
                recommendation="Review stage execution and error handling",
            ))

        if telemetry:
            if telemetry.retry_count > 0:
                lessons.append(Lesson(
                    category="reliability",
                    description=f"Required {telemetry.retry_count} retries",
                    severity="warning",
                    recommendation="Investigate stability of executed stages",
                ))
            if telemetry.recovery_count > 0:
                lessons.append(Lesson(
                    category="recovery",
                    description=f"Recovery triggered {telemetry.recovery_count} times",
                    severity="info",
                    recommendation="Review recovery strategy effectiveness",
                ))

        total_stages = len(mission.stages)
        if total_stages > 10:
            lessons.append(Lesson(
                category="complexity",
                description=f"Mission had {total_stages} stages",
                severity="info",
                recommendation="Consider decomposing into smaller missions",
            ))

        return lessons

    async def _store_experience(self, mission: Mission,
                                 result: ExecutionResult,
                                 report: ReflectionReport) -> str:
        self._experience_count += 1
        exp_id = f"exp-{self._experience_count}"
        if self._plan_memory and hasattr(self._plan_memory, 'store_template'):
            try:
                from app.planning.base import Plan, PlanStep
                plan = Plan(
                    plan_id=exp_id,
                    goal_id="",
                    goal_name=mission.intent,
                    metadata={
                        "experience_type": "mission_reflection",
                        "mission_id": mission.mission_id,
                        "duration_ms": report.total_duration_ms,
                        "lessons": [l.description for l in report.lessons],
                    },
                )
                await self._plan_memory.store_template(exp_id, plan)
            except Exception:
                pass
        return exp_id

    async def _store_learning(self, report: ReflectionReport) -> None:
        if not self._learning_engine:
            return
        try:
            summary = (
                f"Mission {report.mission_id[:8]}: "
                f"{report.stages_completed}/{report.stages_planned} stages, "
                f"{report.total_duration_ms:.0f}ms, "
                f"accuracy={report.planner_accuracy:.0%}"
            )
            self._learning_engine.record_reflection(
                category="mission_reflection",
                description=summary,
                severity="info",
                recommendation="; ".join(report.recommended_improvements[:3]),
                mission_id=report.mission_id,
            )
        except Exception:
            pass
