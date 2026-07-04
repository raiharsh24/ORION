import time
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from loguru import logger

from app.friday.intent import IntentType


@dataclass
class ReasoningStage:
    stage: str
    summary: str
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    reasoning_id: str
    objective: str
    stages: List[ReasoningStage] = field(default_factory=list)
    overall_summary: str = ""
    created_at: float = field(default_factory=time.time)

    def add_stage(self, stage: ReasoningStage) -> None:
        self.stages.append(stage)

    @property
    def total_duration_ms(self) -> float:
        return sum(s.duration_ms for s in self.stages)


class ReasoningPipeline:
    """Multi-step reasoning pipeline with separate stages.

    Stages: Intent Analysis → Capability Analysis → Risk Analysis
    → Tool Selection → Execution Planning → Validation → Reflection.

    Stores reasoning summaries (not chain-of-thought) for transparency.
    Reuses existing IntentAnalyzer patterns.
    """

    STAGES = [
        "intent_analysis",
        "capability_analysis",
        "risk_analysis",
        "tool_selection",
        "execution_planning",
        "validation",
        "reflection",
    ]

    def __init__(self) -> None:
        self._results: Dict[str, ReasoningResult] = {}
        self._total_runs = 0

    async def reason(self, objective: str) -> ReasoningResult:
        start = time.time()
        reasoning_id = str(uuid.uuid4())
        result = ReasoningResult(reasoning_id=reasoning_id, objective=objective)

        # Stage 1: Intent Analysis
        stage_start = time.time()
        intent = self._analyze_intent(objective)
        result.add_stage(ReasoningStage(
            stage="intent_analysis",
            summary=f"Identified intent: {intent['category']} "
                    f"(confidence: {intent['confidence']:.2f})",
            duration_ms=(time.time() - stage_start) * 1000,
            details=intent,
        ))

        # Stage 2: Capability Analysis
        stage_start = time.time()
        capabilities = self._analyze_capabilities(intent)
        result.add_stage(ReasoningStage(
            stage="capability_analysis",
            summary=f"Required capabilities: {', '.join(capabilities['primary'])}",
            duration_ms=(time.time() - stage_start) * 1000,
            details=capabilities,
        ))

        # Stage 3: Risk Analysis
        stage_start = time.time()
        risk = self._analyze_risk(objective, capabilities)
        result.add_stage(ReasoningStage(
            stage="risk_analysis",
            summary=f"Risk level: {risk['level']} (score: {risk['score']:.2f})",
            duration_ms=(time.time() - stage_start) * 1000,
            details=risk,
        ))

        # Stage 4: Tool Selection
        stage_start = time.time()
        tools = self._select_tools(capabilities)
        result.add_stage(ReasoningStage(
            stage="tool_selection",
            summary=f"Selected {len(tools['selected'])} tools",
            duration_ms=(time.time() - stage_start) * 1000,
            details=tools,
        ))

        # Stage 5: Execution Planning
        stage_start = time.time()
        execution_plan = self._plan_execution(objective, tools, risk)
        result.add_stage(ReasoningStage(
            stage="execution_planning",
            summary=f"Planned {execution_plan['step_count']} execution steps",
            duration_ms=(time.time() - stage_start) * 1000,
            details=execution_plan,
        ))

        # Stage 6: Validation
        stage_start = time.time()
        validation = self._validate_plan(execution_plan)
        result.add_stage(ReasoningStage(
            stage="validation",
            summary="Valid" if validation["valid"] else f"Warnings: {len(validation['warnings'])}",
            duration_ms=(time.time() - stage_start) * 1000,
            details=validation,
        ))

        # Stage 7: Reflection
        stage_start = time.time()
        reflection = self._reflect(intent, capabilities, risk, tools, validation)
        result.add_stage(ReasoningStage(
            stage="reflection",
            summary=reflection["summary"],
            duration_ms=(time.time() - stage_start) * 1000,
            details=reflection,
        ))

        result.overall_summary = (
            f"Reasoning: {intent['category']} objective, "
            f"{risk['level']} risk, "
            f"{execution_plan['step_count']} steps planned, "
            f"{'valid' if validation['valid'] else 'needs revision'}"
        )

        total = (time.time() - start) * 1000
        self._results[reasoning_id] = result
        self._total_runs += 1
        logger.info(f"ReasoningPipeline completed in {total:.0f}ms: {result.overall_summary}")
        return result

    def _analyze_intent(self, objective: str) -> Dict[str, Any]:
        obj_lower = objective.lower()
        categories = {
            "organize": ("organization", 0.9),
            "find": ("search", 0.85),
            "create": ("creation", 0.85),
            "build": ("development", 0.9),
            "test": ("testing", 0.85),
            "deploy": ("deployment", 0.8),
            "analyze": ("analysis", 0.85),
            "research": ("research", 0.9),
            "clean": ("maintenance", 0.8),
            "monitor": ("monitoring", 0.85),
            "backup": ("backup", 0.8),
            "install": ("installation", 0.85),
            "update": ("update", 0.8),
            "configure": ("configuration", 0.85),
            "help": ("assistance", 0.7),
        }
        for keyword, (category, confidence) in categories.items():
            if keyword in obj_lower:
                return {"category": category, "confidence": confidence, "keyword": keyword}

        return {"category": "general", "confidence": 0.5, "keyword": "unknown"}

    def _analyze_capabilities(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        capability_map = {
            "organization": {"primary": ["file_management", "categorization"],
                             "secondary": ["search", "knowledge_retrieval"]},
            "search": {"primary": ["knowledge_retrieval", "file_search"],
                       "secondary": ["web_search"]},
            "creation": {"primary": ["code_generation", "file_management"],
                         "secondary": ["tool_execution"]},
            "development": {"primary": ["code_generation", "tool_execution"],
                            "secondary": ["file_management", "validation"]},
            "testing": {"primary": ["code_execution", "validation"],
                        "secondary": ["tool_execution"]},
            "deployment": {"primary": ["tool_execution", "system_control"],
                           "secondary": ["validation"]},
            "analysis": {"primary": ["information_synthesis", "knowledge_retrieval"],
                         "secondary": ["data_analysis"]},
            "research": {"primary": ["web_search", "knowledge_retrieval"],
                         "secondary": ["information_synthesis"]},
            "maintenance": {"primary": ["file_management", "system_control"],
                            "secondary": ["search"]},
            "monitoring": {"primary": ["system_control", "data_analysis"],
                           "secondary": ["notification"]},
            "backup": {"primary": ["file_management", "system_control"],
                       "secondary": ["validation"]},
            "installation": {"primary": ["tool_execution", "system_control"],
                             "secondary": ["file_management"]},
            "update": {"primary": ["tool_execution", "file_management"],
                       "secondary": ["system_control"]},
            "configuration": {"primary": ["file_management", "tool_execution"],
                              "secondary": ["system_control"]},
        }
        return capability_map.get(intent.get("category", "general"), {
            "primary": ["tool_execution"],
            "secondary": [],
        })

    def _analyze_risk(self, objective: str, capabilities: Dict[str, Any]) -> Dict[str, Any]:
        risk_keywords = {
            "delete": 0.3, "remove": 0.3, "destroy": 0.4,
            "overwrite": 0.25, "modify": 0.2, "change": 0.15,
            "install": 0.2, "deploy": 0.25, "execute": 0.15,
            "system": 0.2, "config": 0.15, "network": 0.2,
        }
        obj_lower = objective.lower()
        base_risk = 0.1

        for keyword, risk_bump in risk_keywords.items():
            if keyword in obj_lower:
                base_risk += risk_bump

        if "system_control" in capabilities.get("primary", []):
            base_risk += 0.15

        risk_score = min(base_risk, 0.95)
        if risk_score < 0.2:
            level = "low"
        elif risk_score < 0.4:
            level = "medium"
        else:
            level = "high"

        return {"score": round(risk_score, 2), "level": level, "factors": []}

    def _select_tools(self, capabilities: Dict[str, Any]) -> Dict[str, Any]:
        tool_map = {
            "file_management": "filesystem",
            "categorization": "filesystem",
            "search": "knowledge.search",
            "knowledge_retrieval": "knowledge.search",
            "file_search": "filesystem",
            "web_search": "browser",
            "code_generation": "filesystem",
            "tool_execution": "terminal",
            "code_execution": "terminal",
            "validation": "filesystem",
            "system_control": "terminal",
            "information_synthesis": "knowledge.search",
            "data_analysis": "terminal",
            "notification": "desktop.notifications",
        }

        selected = []
        for cap in capabilities.get("primary", []):
            tool = tool_map.get(cap, "filesystem")
            if tool not in selected:
                selected.append(tool)
        for cap in capabilities.get("secondary", []):
            tool = tool_map.get(cap, "filesystem")
            if tool not in selected:
                selected.append(tool)

        return {"selected": selected, "total": len(selected)}

    def _plan_execution(
        self, objective: str, tools: Dict[str, Any], risk: Dict[str, Any]
    ) -> Dict[str, Any]:
        steps = []
        for tool in tools.get("selected", []):
            steps.append({"tool": tool, "order": len(steps) + 1,
                          "description": f"Execute {tool} for: {objective[:60]}"})

        if risk.get("level") == "high":
            steps.insert(0, {"tool": "filesystem",
                             "order": 0,
                             "description": "Pre-flight safety check"})
            steps.append({"tool": "filesystem",
                          "order": len(steps) + 1,
                          "description": "Verify results"})

        return {"step_count": len(steps), "steps": steps,
                "estimated_duration": len(steps) * 30}

    def _validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        warnings = []
        if plan.get("step_count", 0) == 0:
            warnings.append("No execution steps defined")
        if plan.get("estimated_duration", 0) > 600:
            warnings.append("Estimated duration exceeds 10 minutes")
        return {"valid": len(warnings) == 0, "warnings": warnings}

    def _reflect(
        self, intent: Dict[str, Any], capabilities: Dict[str, Any],
        risk: Dict[str, Any], tools: Dict[str, Any],
        validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        summary_parts = []
        summary_parts.append(f"Intent: {intent.get('category', 'unknown')}")
        summary_parts.append(f"Risk: {risk.get('level', 'unknown')}")
        summary_parts.append(f"Tools: {tools.get('total', 0)}")
        summary_parts.append(f"Valid: {validation.get('valid', False)}")
        return {"summary": " | ".join(summary_parts), "recommendations": []}

    def get_result(self, reasoning_id: str) -> Optional[ReasoningResult]:
        return self._results.get(reasoning_id)

    def list_results(self, limit: int = 10) -> List[ReasoningResult]:
        results = sorted(
            self._results.values(),
            key=lambda r: r.created_at, reverse=True
        )
        return results[:limit]

    def get_stats(self) -> Dict[str, Any]:
        return {"total_runs": self._total_runs, "cached_results": len(self._results)}
