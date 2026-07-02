from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


class DispatchStrategy(Enum):
    SINGLE_AGENT = "single_agent"
    PARALLEL_AGENTS = "parallel_agents"
    WORKFLOW_ENGINE = "workflow_engine"
    TOOL_EXECUTION = "tool_execution"
    PLUGIN_EXECUTION = "plugin_execution"


@dataclass
class DispatchDecision:
    strategy: DispatchStrategy
    agent_ids: List[str] = field(default_factory=list)
    workflow_id: Optional[str] = None
    tool_id: Optional[str] = None
    plugin_id: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""


class Dispatcher:
    def __init__(self, agent_manager: Any = None,
                 workflow_engine: Any = None,
                 tool_executor: Any = None,
                 plugin_runtime: Any = None):
        self._agent_manager = agent_manager
        self._workflow_engine = workflow_engine
        self._tool_executor = tool_executor
        self._plugin_runtime = plugin_runtime

    def dispatch(self, mission: Any) -> DispatchDecision:
        intent = getattr(mission, 'intent', '') or ''
        user_request = getattr(mission, 'user_request', '') or ''
        goal_ids = getattr(mission, 'goal_ids', []) or []
        metadata = getattr(mission, 'metadata', {}) or {}

        preferred = metadata.get("dispatch_strategy", "")
        if preferred:
            try:
                strategy = DispatchStrategy(preferred)
                return DispatchDecision(
                    strategy=strategy, reason=f"User-specified strategy: {preferred}",
                )
            except ValueError:
                pass

        workflow_keywords = ["workflow", "step by step", "sequence"]
        if any(kw in user_request.lower() for kw in workflow_keywords):
            return DispatchDecision(
                strategy=DispatchStrategy.WORKFLOW_ENGINE,
                reason="User request contains workflow keywords",
            )

        plugin_keywords = ["plugin", "extension", "addon"]
        if any(kw in user_request.lower() for kw in plugin_keywords):
            return DispatchDecision(
                strategy=DispatchStrategy.PLUGIN_EXECUTION,
                reason="User request contains plugin keywords",
            )

        if self._agent_manager and len(goal_ids) > 1:
            agents = self._agent_manager.list_agents() if hasattr(self._agent_manager, 'list_agents') else []
            if len(agents) >= 2:
                return DispatchDecision(
                    strategy=DispatchStrategy.PARALLEL_AGENTS,
                    agent_ids=[a.agent_id for a in agents[:3]],
                    reason=f"Multiple goals ({len(goal_ids)}) with available agents",
                )
            elif agents:
                return DispatchDecision(
                    strategy=DispatchStrategy.SINGLE_AGENT,
                    agent_ids=[agents[0].agent_id],
                    reason="Single agent available for dispatch",
                )

        tool_keywords = ["execute", "run", "process", "transform"]
        if any(kw in user_request.lower() for kw in tool_keywords):
            return DispatchDecision(
                strategy=DispatchStrategy.TOOL_EXECUTION,
                reason="User request contains tool keywords",
            )

        if self._agent_manager:
            agents = self._agent_manager.list_agents() if hasattr(self._agent_manager, 'list_agents') else []
            if agents:
                return DispatchDecision(
                    strategy=DispatchStrategy.SINGLE_AGENT,
                    agent_ids=[agents[0].agent_id],
                    reason="Default: single agent dispatch",
                )

        return DispatchDecision(
            strategy=DispatchStrategy.WORKFLOW_ENGINE,
            reason="Default: workflow engine dispatch",
        )

    @property
    def available(self) -> bool:
        return (self._agent_manager is not None or
                self._workflow_engine is not None)
