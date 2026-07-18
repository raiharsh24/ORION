from typing import Dict, Any, Optional

from app.tools.base import ToolDefinition, ToolHealth, PermissionLevel
from app.tool_selection.base import ToolSelectionContext
from app.tool_selection.rules import SelectionRules


WEIGHT_INTENT_MATCH = 25.0
WEIGHT_HEALTH = 20.0
WEIGHT_LATENCY = 15.0
WEIGHT_COST = 10.0
WEIGHT_STREAMING = 10.0
WEIGHT_PARALLEL = 10.0
WEIGHT_PERMISSION = 5.0
WEIGHT_CATEGORY_MATCH = 5.0
WEIGHT_KEYWORD_OVERLAP = 15.0
WEIGHT_PARAMETER_COMPATIBILITY = 8.0
WEIGHT_ENABLED = 2.0

MAX_POSSIBLE_SCORE = (
    WEIGHT_INTENT_MATCH + WEIGHT_HEALTH + WEIGHT_LATENCY + WEIGHT_COST
    + WEIGHT_STREAMING + WEIGHT_PARALLEL + WEIGHT_PERMISSION
    + WEIGHT_CATEGORY_MATCH + WEIGHT_KEYWORD_OVERLAP
    + WEIGHT_PARAMETER_COMPATIBILITY + WEIGHT_ENABLED + 15.0
)


class ToolScorer:
    def __init__(self, context: ToolSelectionContext,
                 optimizer_recommendations: Optional[Dict[str, Any]] = None) -> None:
        self._context = context
        self._optimizer = optimizer_recommendations or {}

    def score(self, tool: ToolDefinition) -> float:
        s = 0.0

        s += self._score_intent_match(tool)
        s += self._score_health(tool)
        s += self._score_latency(tool)
        s += self._score_cost(tool)
        s += self._score_streaming(tool)
        s += self._score_parallel(tool)
        s += self._score_permission(tool)
        s += self._score_category_match(tool)
        s += self._score_keyword_overlap(tool)
        s += self._score_parameter_compatibility(tool)
        s += self._score_enabled(tool)
        s += self._score_optimizer(tool)

        return round(s, 4)

    def compute_confidence(self, score: float) -> float:
        return round(min(1.0, max(0.0, score / MAX_POSSIBLE_SCORE)), 4)

    def build_reasoning(self, tool: ToolDefinition) -> str:
        parts = []
        if self._score_intent_match(tool) > 0:
            parts.append("intent match")
        if SelectionRules.matches_category(tool, self._context):
            parts.append("category match")
        kw = self._score_keyword_overlap(tool)
        if kw > 0:
            parts.append(f"keyword overlap ({kw:.0%})")
        if SelectionRules.has_permission(tool, self._context):
            parts.append("permission ok")
        if tool.health.status == "healthy":
            parts.append("healthy")
        pm = self._score_parameter_compatibility(tool)
        if pm > 0.5:
            parts.append("params compatible")
        if self._context.prefer_streaming and tool.supports_streaming:
            parts.append("supports streaming")
        if self._context.prefer_parallel and tool.supports_parallel_execution:
            parts.append("supports parallel")
        recommended = self._optimizer.get("recommended_tools", [])
        if tool.id in recommended:
            parts.append("optimizer recommended")
        return "; ".join(parts) if parts else "eligible"

    def _score_intent_match(self, tool: ToolDefinition) -> float:
        if not self._context.intent:
            return 0.0
        intent = self._context.intent.value if hasattr(self._context.intent, "value") else str(self._context.intent)
        if SelectionRules.matches_intent(tool, intent):
            return WEIGHT_INTENT_MATCH
        return 0.0

    def _score_health(self, tool: ToolDefinition) -> float:
        if tool.health.status == "healthy":
            return WEIGHT_HEALTH
        elif tool.health.status == "unknown":
            return WEIGHT_HEALTH * 0.5
        elif tool.health.status == "warning":
            return WEIGHT_HEALTH * 0.25
        return 0.0

    def _score_latency(self, tool: ToolDefinition) -> float:
        if not self._context.pipeline_metadata:
            return WEIGHT_LATENCY * 0.5
        max_latency = self._context.pipeline_metadata.get("max_tool_latency_ms", 5000)
        if max_latency <= 0:
            return WEIGHT_LATENCY * 0.5
        if tool.estimated_latency_ms <= max_latency:
            ratio = 1.0 - (tool.estimated_latency_ms / max_latency)
            return WEIGHT_LATENCY * max(0.1, ratio)
        return WEIGHT_LATENCY * 0.1

    def _score_cost(self, tool: ToolDefinition) -> float:
        if not self._context.pipeline_metadata:
            return WEIGHT_COST * 0.5
        budget = self._context.pipeline_metadata.get("tool_cost_budget", 10.0)
        if budget <= 0:
            return WEIGHT_COST * 0.5
        if tool.estimated_cost <= budget:
            ratio = 1.0 - (tool.estimated_cost / budget)
            return WEIGHT_COST * max(0.1, ratio)
        return WEIGHT_COST * 0.1

    def _score_streaming(self, tool: ToolDefinition) -> float:
        if self._context.prefer_streaming and tool.supports_streaming:
            return WEIGHT_STREAMING
        return 0.0

    def _score_parallel(self, tool: ToolDefinition) -> float:
        if self._context.prefer_parallel and tool.supports_parallel_execution:
            return WEIGHT_PARALLEL
        return 0.0

    def _score_permission(self, tool: ToolDefinition) -> float:
        if SelectionRules.has_permission(tool, self._context):
            return WEIGHT_PERMISSION
        return 0.0

    def _score_category_match(self, tool: ToolDefinition) -> float:
        if SelectionRules.matches_category(tool, self._context):
            return WEIGHT_CATEGORY_MATCH
        return 0.0

    def _score_keyword_overlap(self, tool: ToolDefinition) -> float:
        query = self._context.relevance_query or (
            self._context.intent.value if hasattr(self._context.intent, "value") else str(self._context.intent)
        )
        overlap = SelectionRules.keyword_overlap(query, tool)
        return WEIGHT_KEYWORD_OVERLAP * overlap

    def _score_parameter_compatibility(self, tool: ToolDefinition) -> float:
        compat = SelectionRules.parameter_compatibility(self._context, tool)
        return WEIGHT_PARAMETER_COMPATIBILITY * compat

    def _score_enabled(self, tool: ToolDefinition) -> float:
        if getattr(tool, "enabled", True):
            return WEIGHT_ENABLED
        return 0.0

    def _score_optimizer(self, tool: ToolDefinition) -> float:
        recommended = self._optimizer.get("recommended_tools", [])
        if tool.id in recommended:
            return 15.0
        discouraged = self._optimizer.get("discouraged_tools", [])
        if tool.id in discouraged:
            return -15.0
        return 0.0
