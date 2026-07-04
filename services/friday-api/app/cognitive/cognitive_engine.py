import asyncio
import time
from typing import Dict, Any, Optional, List
from loguru import logger

from app.events.bus import EventBus
from app.tool_execution.executor import ToolExecutionEngine
from app.cognitive.goal_memory import GoalMemory
from app.cognitive.adaptive_learning import AdaptiveLearning
from app.cognitive.confidence_v2 import ConfidenceEngineV2
from app.cognitive.reflection_v2 import ReflectionV2
from app.cognitive.goal_manager import HierarchicalGoalManager
from app.cognitive.autonomous_scheduler import AutonomousScheduler
from app.cognitive.collaborative_orchestrator import CollaborativeOrchestrator
from app.cognitive.events import SchedulerStarted, SchedulerStopped, LearningUpdated
from app.cognitive.consolidation import CognitiveConsolidation


class CognitiveEngine:
    def __init__(self, event_bus: Optional[EventBus] = None,
                 memory_engine: Any = None,
                 planner_engine: Any = None,
                 mission_executor: Any = None,
                 learning_engine: Any = None,
                 confidence_engine: Any = None,
                 reflection_engine: Any = None,
                 adaptive_scheduler: Any = None,
                 tool_execution_engine: Optional[ToolExecutionEngine] = None) -> None:
        self._event_bus = event_bus
        self._memory_engine = memory_engine
        self._planner_engine = planner_engine
        self._mission_executor = mission_executor
        self._learning_engine = learning_engine
        self._confidence_engine = confidence_engine
        self._reflection_engine = reflection_engine
        self._adaptive_scheduler = adaptive_scheduler
        self._tool_execution_engine = tool_execution_engine

        self._store = None
        if memory_engine and hasattr(memory_engine, '_manager') and memory_engine._manager:
            self._store = memory_engine._manager._store

        self._goal_memory = GoalMemory(
            store=self._store, event_bus=event_bus,
        )
        self._goal_memory.load()
        self._goal_memory.set_on_save(self._on_goal_save)

        self._adaptive_learning = AdaptiveLearning(
            learning_engine=learning_engine,
            goal_memory=self._goal_memory,
        )

        self._confidence_v2 = ConfidenceEngineV2(
            confidence_engine=confidence_engine,
            adaptive_learning=self._adaptive_learning,
        )

        self._reflection_v2 = ReflectionV2(
            learning_engine=learning_engine,
            reflection_engine=reflection_engine,
            goal_memory=self._goal_memory,
            adaptive_learning=self._adaptive_learning,
        )

        self._goal_manager = HierarchicalGoalManager(
            goal_memory=self._goal_memory,
            goal_planner=planner_engine,
        )

        self._autonomous_scheduler = AutonomousScheduler(
            mission_executor=mission_executor,
            adaptive_scheduler=adaptive_scheduler,
        )
        self._register_scheduler_handler()

        self._cognitive_consolidation = CognitiveConsolidation(
            goal_memory=self._goal_memory,
        )

        self._orchestrator: Optional[CollaborativeOrchestrator] = None

    def _on_goal_save(self) -> None:
        pass

    def _register_scheduler_handler(self) -> None:
        async def scheduler_handler(mission: Any) -> None:
            if self._mission_executor and hasattr(mission, 'objective'):
                try:
                    from app.workflow_engine.base import WorkflowGraph, WorkflowStep
                    step = WorkflowStep(
                        id=f"sched_{mission.mission_id}",
                        node_id="cognitive-agent",
                        step_type="tool_execution",
                        config={"objective": mission.objective},
                    )
                    graph = WorkflowGraph(
                        workflow_id=f"sched_{mission.mission_id}",
                        steps=[step],
                    )
                    self._mission_executor.register_workflow_graph(
                        graph.workflow_id, graph,
                    )
                    created = self._mission_executor.create_mission(
                        name=mission.objective[:80],
                        workflow_graphs={graph.workflow_id: graph},
                        metadata={"source": "cognitive_scheduler"},
                    )
                    await self._mission_executor.start_mission(created.id)
                    logger.info(
                        f"CognitiveEngine: Scheduler routed '{mission.objective[:60]}' "
                        f"to MissionExecutor ({created.id[:8]})"
                    )
                except Exception as e:
                    logger.error(
                        f"CognitiveEngine: Scheduler handler failed: {e}"
                    )

        self._autonomous_scheduler.register_handler("once", scheduler_handler)
        self._autonomous_scheduler.register_handler("recurring", scheduler_handler)

    @property
    def goal_memory(self) -> GoalMemory:
        return self._goal_memory

    @property
    def adaptive_learning(self) -> AdaptiveLearning:
        return self._adaptive_learning

    @property
    def confidence_v2(self) -> ConfidenceEngineV2:
        return self._confidence_v2

    @property
    def reflection_v2(self) -> ReflectionV2:
        return self._reflection_v2

    @property
    def goal_manager(self) -> HierarchicalGoalManager:
        return self._goal_manager

    @property
    def autonomous_scheduler(self) -> AutonomousScheduler:
        return self._autonomous_scheduler

    @property
    def orchestrator(self) -> Optional[CollaborativeOrchestrator]:
        return self._orchestrator

    def get_or_create_orchestrator(self) -> CollaborativeOrchestrator:
        if not self._orchestrator:
            from app.planner.goal_planner import GoalPlanner
            planner = self._planner_engine or GoalPlanner()
            self._orchestrator = CollaborativeOrchestrator(
                goal_planner=planner,
                mission_executor=self._mission_executor,
                event_bus=self._event_bus,
                knowledge_graph=(
                    self._memory_engine.graph
                    if self._memory_engine and hasattr(self._memory_engine, 'graph')
                    else None
                ),
                episodic_memory=(
                    self._memory_engine.episodic
                    if self._memory_engine and hasattr(self._memory_engine, 'episodic')
                    else None
                ),
                hierarchical_goal_manager=self._goal_manager,
                adaptive_learning=self._adaptive_learning,
                reflection_v2=self._reflection_v2,
                autonomous_scheduler=self._autonomous_scheduler,
                tool_execution_engine=self._tool_execution_engine,
            )
        return self._orchestrator

    async def run_cognitive_mission(self, objective: str,
                                     description: str = "",
                                     require_approval: bool = False,
                                     use_collaboration: bool = True,
                                     use_scheduler: bool = False,
                                     delay_seconds: float = 0.0,
                                     use_mission_executor: bool = False) -> Dict[str, Any]:
        orchestrator = self.get_or_create_orchestrator()
        result = await orchestrator.run_cognitive_mission(
            objective=objective,
            description=description,
            require_approval=require_approval,
            use_hierarchy=True,
            use_collaboration=use_collaboration,
            use_scheduler=use_scheduler,
            delay_seconds=delay_seconds,
            use_mission_executor=use_mission_executor,
        )

        if self._goal_memory:
            self._goal_memory.save()

        if self._adaptive_learning and result.get("collaboration"):
            try:
                self._adaptive_learning.refresh_from_history()
                self._publish(LearningUpdated(
                    learning_type="adaptive_refresh",
                    summary=self._adaptive_learning.get_summary(),
                ))
            except Exception:
                pass

        return result

    async def start_scheduler(self) -> None:
        await self._autonomous_scheduler.start_background()
        self._publish(SchedulerStarted())

    async def stop_scheduler(self) -> None:
        await self._autonomous_scheduler.shutdown()
        self._publish(SchedulerStopped())

    async def start_consolidation(self) -> None:
        await self._cognitive_consolidation.start()

    async def stop_consolidation(self) -> None:
        await self._cognitive_consolidation.stop()

    async def run_consolidation(self) -> Dict[str, Any]:
        return await self._cognitive_consolidation.run_consolidation()

    @property
    def consolidation(self) -> CognitiveConsolidation:
        return self._cognitive_consolidation

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass

    def get_strategic_context(self) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        if self._goal_memory:
            context["goals"] = self._goal_memory.get_strategic_context()
        if self._adaptive_learning:
            context["learning"] = self._adaptive_learning.get_summary()
        if self._autonomous_scheduler:
            context["scheduler"] = self._autonomous_scheduler.get_stats()
        return context

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY",
            "goal_memory": self._goal_memory.get_stats() if self._goal_memory else {},
            "adaptive_learning": self._adaptive_learning.get_summary() if self._adaptive_learning else {},
            "confidence_v2": self._confidence_v2.get_stats() if self._confidence_v2 else {},
            "reflection_v2": self._reflection_v2.get_stats() if self._reflection_v2 else {},
            "goal_manager": self._goal_manager.get_stats() if self._goal_manager else {},
            "autonomous_scheduler": self._autonomous_scheduler.get_stats() if self._autonomous_scheduler else {},
            "consolidation": self._cognitive_consolidation.health() if self._cognitive_consolidation else {},
            "orchestrator": (
                self._orchestrator.health()
                if self._orchestrator else {"status": "NOT_CREATED"}
            ),
        }
