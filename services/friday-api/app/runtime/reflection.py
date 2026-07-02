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


class ReflectionEngine:
    def __init__(self, plan_memory: Any = None):
        self._plan_memory = plan_memory
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

        if execution_result.success:
            report.experience_id = await self._store_experience(
                mission, execution_result, report,
            )

        return report

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
