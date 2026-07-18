import time
from typing import Dict, Any, List, Optional, Set
from loguru import logger

from app.events.bus import EventBus
from app.tools.base import ToolDefinition, PermissionLevel
from app.tools.registry import ToolRegistry
from app.tool_selection.base import ToolSelectionContext, SelectedTool, ToolSelectionResult
from app.tool_selection.rules import SelectionRules
from app.tool_selection.score import ToolScorer
from app.tool_selection.events import (
    ToolSelectionStarted, ToolSelected, FallbackToolSelected, ToolSelectionCompleted,
)


class ToolSelectionEngine:
    def __init__(self, tool_registry: ToolRegistry,
                 event_bus: Optional[EventBus] = None) -> None:
        self._tool_registry = tool_registry
        self._event_bus = event_bus
        self._selection_count = 0
        self._fallback_count = 0
        self._total_latency_ms = 0.0

    async def select(self, context: ToolSelectionContext) -> ToolSelectionResult:
        t0 = time.time()
        result = ToolSelectionResult()

        self._publish(ToolSelectionStarted(
            intent=str(context.intent.value) if hasattr(context.intent, "value") else str(context.intent),
            context={
                "required_categories": context.required_categories,
                "required_capabilities": context.required_capabilities,
                "user_permission_level": context.user_permission_level.value,
            },
        ))

        all_tools = self._tool_registry.list_tools()
        result.candidate_count = len(all_tools)

        candidates = self._filter_candidates(all_tools, context)
        if not candidates:
            result.warnings.append("No eligible tools found")
            result.confidence = 0.0
            result.selection_latency_ms = (time.time() - t0) * 1000
            self._publish(ToolSelectionCompleted(
                intent=str(context.intent),
                selected_count=0, fallback_count=0,
                confidence=0.0, latency_ms=result.selection_latency_ms,
            ))
            return result

        scorer = ToolScorer(context, context.optimizer_recommendations)
        scored = [(t, scorer.score(t)) for t in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        TOP_N = 3
        tool_by_id = {t.id: t for t, _ in scored}

        # Build set of tool IDs to process: top N primaries + their required deps
        process_ids: Set[str] = set()
        for tool, _ in scored[:TOP_N]:
            process_ids.add(tool.id)
            for dep in tool.dependencies:
                if not dep.optional and dep.tool_id in tool_by_id:
                    process_ids.add(dep.tool_id)

        # Build dependency-safe processing order via DFS
        process_order: List[ToolDefinition] = []
        visited: Set[str] = set()

        def _add_with_deps(tid: str) -> None:
            if tid in visited:
                return
            visited.add(tid)
            t = tool_by_id.get(tid)
            if t is None:
                return
            for dep in t.dependencies:
                if not dep.optional and dep.tool_id in process_ids:
                    _add_with_deps(dep.tool_id)
            process_order.append(t)

        for tid in process_ids:
            _add_with_deps(tid)

        seen_ids: Set[str] = set()
        for tool in process_order:
            if tool.id in seen_ids:
                continue
            score = scorer.score(tool)
            confidence = scorer.compute_confidence(score)
            reasoning = scorer.build_reasoning(tool)

            # Determine if this is a primary selection or a dependency
            is_primary = tool.id in {t.id for t, _ in scored[:TOP_N]}

            if is_primary:
                primary = self._try_select(tool, context, seen_ids)
                if primary is not None:
                    primary.score = score
                    primary.confidence = confidence
                    primary.selection_reason = reasoning
                    result.selected_tools.append(primary)
                    result.selection_scores[tool.id] = score
                    result.selection_reasons[tool.id] = reasoning
                    seen_ids.add(tool.id)
                    self._publish(ToolSelected(
                        tool_id=tool.id, name=tool.name,
                        score=score, reason=reasoning,
                    ))

                    for dep in tool.dependencies:
                        if dep.tool_id not in seen_ids and dep.tool_id in tool_by_id:
                            dep_tool = tool_by_id[dep.tool_id]
                            dep_selected = SelectedTool(
                                tool=dep_tool,
                                score=1.0,
                                selection_reason=f"Dependency of {tool.id}",
                                is_fallback=False,
                                confidence=1.0,
                            )
                            result.selected_tools.append(dep_selected)
                            result.selection_scores[dep_tool.id] = 1.0
                            result.selection_reasons[dep_tool.id] = f"Dependency of {tool.id}"
                            seen_ids.add(dep_tool.id)
                else:
                    fallback = self._find_fallback(tool, context, seen_ids, score, confidence)
                    if fallback is not None:
                        result.fallback_tools.append(fallback)
                        result.selected_tools.append(fallback)
                        result.selection_scores[fallback.tool.id] = fallback.score
                        result.selection_reasons[fallback.tool.id] = fallback.selection_reason
                        seen_ids.add(fallback.tool.id)
                        self._fallback_count += 1
            else:
                # Dependency-only tool: add if healthy
                if SelectionRules.is_healthy(tool) and SelectionRules.dependencies_satisfied(tool, seen_ids | {tool.id}):
                    dep_selected = SelectedTool(
                        tool=tool,
                        score=score,
                        selection_reason=f"Dependency of top-ranked tool",
                        is_fallback=False,
                        confidence=confidence,
                    )
                    result.selected_tools.append(dep_selected)
                    result.selection_scores[tool.id] = score
                    result.selection_reasons[tool.id] = f"Dependency of top-ranked tool"
                    seen_ids.add(tool.id)

        if result.selected_tools:
            result.estimated_total_latency_ms = sum(
                st.tool.estimated_latency_ms for st in result.selected_tools
            )
            result.estimated_total_cost = sum(
                st.tool.estimated_cost for st in result.selected_tools
            )

        total = len(result.selected_tools)
        selected = total - len(result.fallback_tools)
        result.confidence = round(selected / max(total, 1), 4)

        result.selection_latency_ms = (time.time() - t0) * 1000
        self._selection_count += 1
        self._total_latency_ms += result.selection_latency_ms

        self._publish(ToolSelectionCompleted(
            intent=str(context.intent),
            selected_count=len(result.selected_tools),
            fallback_count=len(result.fallback_tools),
            confidence=result.confidence,
            latency_ms=result.selection_latency_ms,
        ))

        return result

    def _filter_candidates(self, tools: List[ToolDefinition],
                           context: ToolSelectionContext) -> List[ToolDefinition]:
        candidates = []
        for tool in tools:
            if not SelectionRules.is_available(tool):
                continue
            if not SelectionRules.has_permission(tool, context):
                continue
            if not SelectionRules.matches_category(tool, context):
                continue
            if not SelectionRules.matches_capability(tool, context):
                continue
            candidates.append(tool)
        return candidates

    def _try_select(self, tool: ToolDefinition, context: ToolSelectionContext,
                    already_selected: Set[str]) -> Optional[SelectedTool]:
        if not SelectionRules.is_healthy(tool):
            return None
        if not SelectionRules.dependencies_satisfied(tool, already_selected | {tool.id}):
            return None
        return SelectedTool(
            tool=tool,
            selection_reason="Best match by scoring",
            is_fallback=False,
        )

    def _find_fallback(self, original: ToolDefinition, context: ToolSelectionContext,
                       already_selected: Set[str], original_score: float = 0.0,
                       original_confidence: float = 0.0) -> Optional[SelectedTool]:
        same_category = self._tool_registry.get_by_category(original.category)
        alternatives = [
            t for t in same_category
            if t.id != original.id
            and t.id not in already_selected
            and SelectionRules.is_available(t)
            and SelectionRules.is_healthy(t)
            and SelectionRules.has_permission(t, context)
            and SelectionRules.dependencies_satisfied(t, already_selected | {t.id})
        ]
        if not alternatives:
            return None
        alternatives.sort(key=lambda t: (
            -t.health.success_count if t.health.success_count > 0 else 0,
            t.estimated_latency_ms,
        ))
        best = alternatives[0]
        self._publish(FallbackToolSelected(
            tool_id=best.id, name=best.name,
            original_tool_id=original.id,
            reason=f"{original.id} unavailable, falling back to {best.id}",
        ))
        return SelectedTool(
            tool=best,
            score=0.5,
            selection_reason=f"Fallback from {original.id}",
            is_fallback=True,
            confidence=original_confidence * 0.7,
        )

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "selection_count": self._selection_count,
            "fallback_count": self._fallback_count,
            "average_latency_ms": round(
                self._total_latency_ms / max(self._selection_count, 1), 2
            ),
        }

    def _publish(self, event: Any) -> None:
        if self._event_bus is not None:
            try:
                self._event_bus.publish(event)
            except Exception:
                pass
