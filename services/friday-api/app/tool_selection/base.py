from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.intent.types import IntentType
from app.tools.base import ToolDefinition, PermissionLevel


@dataclass
class ToolSelectionContext:
    intent: IntentType = IntentType.UNKNOWN
    strategy: Optional[Any] = None
    execution_plan: Optional[Any] = None
    optimizer_recommendations: Optional[Dict[str, Any]] = None
    pipeline_metadata: Optional[Dict[str, Any]] = None
    user_permission_level: PermissionLevel = PermissionLevel.USER
    required_categories: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    prefer_streaming: bool = False
    prefer_parallel: bool = False
    relevance_query: str = ""


@dataclass
class SelectedTool:
    tool: ToolDefinition
    score: float = 0.0
    selection_reason: str = ""
    is_fallback: bool = False
    confidence: float = 0.0


@dataclass
class ToolSelectionResult:
    selected_tools: List[SelectedTool] = field(default_factory=list)
    selection_scores: Dict[str, float] = field(default_factory=dict)
    selection_reasons: Dict[str, str] = field(default_factory=dict)
    fallback_tools: List[SelectedTool] = field(default_factory=list)
    estimated_total_latency_ms: float = 0.0
    estimated_total_cost: float = 0.0
    confidence: float = 1.0
    candidate_count: int = 0
    selection_latency_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def tool_ids(self) -> List[str]:
        return [st.tool.id for st in self.selected_tools]

    @property
    def fallback_tool_ids(self) -> List[str]:
        return [st.tool.id for st in self.fallback_tools]
