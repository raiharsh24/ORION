"""
Universal Tool Registry API.

Exposes the Universal Tool Registry for tool discovery, metadata, health,
execution, and administration. All endpoints respect auth via the global
AuthMiddleware when FRIDAY_AUTH_DISABLED is False.

Static paths (/tools/search, /tools/health, /tools/capabilities,
/tools/select, /tools/execute) are declared BEFORE the parameterized
/tools/{tool_id} so the latter does not shadow them.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.kernel.kernel import FridayKernel
from app.tools.base import PermissionLevel

router = APIRouter()


def _get_registry():
    kernel = FridayKernel.get_instance()
    registry = kernel.get_service("universal_tool_registry") if kernel else None
    if not registry:
        raise HTTPException(status_code=503, detail="Universal Tool Registry not available")
    return registry


def _get_selection_engine():
    kernel = FridayKernel.get_instance()
    engine = kernel.get_service("tool_selection_engine") if kernel else None
    if not engine:
        raise HTTPException(status_code=503, detail="Tool Selection Engine not available")
    return engine


def _get_execution_engine():
    kernel = FridayKernel.get_instance()
    engine = kernel.get_service("tool_execution_engine") if kernel else None
    if not engine:
        raise HTTPException(status_code=503, detail="Tool Execution Engine not available")
    return engine


def _tool_to_dict(tool: Any) -> Dict[str, Any]:
    health = getattr(tool, "health", None)
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "category": tool.category.value if hasattr(tool.category, "value") else str(tool.category),
        "version": tool.version,
        "author": tool.author,
        "tags": list(tool.tags),
        "permission_level": tool.permission_level.value if hasattr(tool.permission_level, "value") else str(tool.permission_level),
        "enabled": getattr(tool, "enabled", True),
        "estimated_cost": tool.estimated_cost,
        "estimated_latency_ms": tool.estimated_latency_ms,
        "supports_streaming": tool.supports_streaming,
        "supports_cancellation": tool.supports_cancellation,
        "supports_parallel_execution": tool.supports_parallel_execution,
        "parameters": [
            {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "required": p.required,
                "default": p.default,
                "enum_values": p.enum_values,
            }
            for p in getattr(tool, "parameters", [])
        ],
        "examples": [
            {
                "prompt": e.prompt,
                "args": e.args,
                "description": e.description,
            }
            for e in getattr(tool, "examples", [])
        ],
        "health": {
            "status": health.status if health else "unknown",
            "last_checked": str(health.last_checked) if health and getattr(health, "last_checked", None) else "",
            "message": health.message if health else "",
            "error_count": health.error_count if health else 0,
            "success_count": health.success_count if health else 0,
            "average_latency_ms": health.average_latency_ms if health else 0.0,
        } if health else None,
        "dependencies": [
            {"tool_id": d.tool_id, "optional": d.optional, "version_requirement": d.version_requirement}
            for d in getattr(tool, "dependencies", [])
        ],
    }


@router.get("/tools")
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Free-text search in name/description/id"),
    enabled_only: Optional[bool] = Query(None, description="Filter by enabled status"),
) -> Dict[str, Any]:
    registry = _get_registry()
    tools = registry.list_tools()
    if enabled_only is True:
        tools = [t for t in tools if getattr(t, "enabled", True)]
    if enabled_only is False:
        tools = [t for t in tools if not getattr(t, "enabled", True)]
    if category:
        tools = [t for t in tools if t.category.value == category or t.category == category]
    if q:
        ql = q.lower()
        tools = [t for t in tools if ql in t.name.lower() or ql in t.description.lower() or ql in t.id.lower()]
    return {
        "count": len(tools),
        "tools": [_tool_to_dict(t) for t in tools],
    }


@router.get("/tools/search")
async def search_tools(
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, description="Maximum results"),
) -> Dict[str, Any]:
    registry = _get_registry()
    results = registry.search(q, limit=limit)
    return {
        "count": len(results),
        "query": q,
        "tools": [_tool_to_dict(t) for t in results],
    }


@router.get("/tools/health")
async def tools_health() -> Dict[str, Any]:
    registry = _get_registry()
    health = registry.registry_health()
    return health.to_dict() if hasattr(health, "to_dict") else dict(health.__dict__)


@router.get("/tools/capabilities")
async def tools_capabilities() -> Dict[str, Any]:
    """List capabilities resolved from the registered tools (discovery)."""
    registry = _get_registry()
    tools = registry.list_tools()
    categories = sorted({t.category.value if hasattr(t.category, "value") else str(t.category) for t in tools})
    return {
        "total_tools": len(tools),
        "enabled_tools": len(registry.get_enabled_tools()),
        "disabled_tools": len(registry.get_disabled_tools()),
        "categories": categories,
        "tool_ids": [t.id for t in tools],
    }


@router.post("/tools/select")
async def select_tools(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the ToolSelectionEngine for a given intent/category (discovery/debug)."""
    from app.intent.types import IntentType
    from app.tool_selection.base import ToolSelectionContext

    intent_str = payload.get("intent", "UNKNOWN")
    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.UNKNOWN
    ctx = ToolSelectionContext(
        intent=intent,
        user_permission_level=PermissionLevel(
            payload.get("user_permission_level", "admin")
        ),
        required_categories=payload.get("required_categories", []),
        required_capabilities=payload.get("required_capabilities", []),
    )
    engine = _get_selection_engine()
    result = await engine.select(ctx)
    return {
        "candidate_count": result.candidate_count,
        "selected_tool_ids": result.tool_ids,
        "confidence": result.confidence,
        "selection_latency_ms": result.selection_latency_ms,
        "selected_tools": [
            {
                "id": st.tool.id,
                "name": st.tool.name,
                "score": st.score,
                "reason": st.selection_reason,
                "is_fallback": st.is_fallback,
            }
            for st in result.selected_tools
        ],
    }


@router.post("/tools/execute")
async def execute_tools(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one or more tools by ID with given arguments."""
    from app.tool_selection.base import ToolSelectionResult, SelectedTool

    tool_ids = payload.get("tool_ids", [])
    args_map = payload.get("args", {})

    if not tool_ids:
        raise HTTPException(status_code=400, detail="tool_ids is required")

    registry = _get_registry()
    selected_tools = []
    for tid in tool_ids:
        td = registry.get(tid)
        if td is None:
            raise HTTPException(status_code=404, detail=f"Tool '{tid}' not found")
        if not getattr(td, "enabled", True):
            raise HTTPException(status_code=400, detail=f"Tool '{tid}' is disabled")
        selected_tools.append(SelectedTool(
            tool=td,
            score=1.0,
            selection_reason="direct execute",
            is_fallback=False,
        ))

    selection_result = ToolSelectionResult(
        selected_tools=selected_tools,
        candidate_count=len(selected_tools),
        confidence=1.0,
    )

    engine = _get_execution_engine()
    result = await engine.execute(selection_result, args_overrides=args_map)

    return {
        "execution_id": result.execution_id,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "mode": result.mode.value if hasattr(result.mode, "value") else str(result.mode),
        "results": [
            {
                "tool_id": r.tool_id,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "output": str(r.output) if r.output else None,
                "error": r.error,
                "duration_ms": r.duration_ms,
                "retries": r.retries,
            }
            for r in result.results
        ],
        "report": result.report,
    }


@router.post("/tools/{tool_id}/enable")
async def enable_tool(tool_id: str) -> Dict[str, Any]:
    registry = _get_registry()
    if registry.get(tool_id) is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    registry.set_enabled(tool_id, True)
    return {"id": tool_id, "enabled": True}


@router.post("/tools/{tool_id}/disable")
async def disable_tool(tool_id: str) -> Dict[str, Any]:
    registry = _get_registry()
    if registry.get(tool_id) is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    registry.set_enabled(tool_id, False)
    return {"id": tool_id, "enabled": False}


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str) -> Dict[str, Any]:
    registry = _get_registry()
    td = registry.get(tool_id)
    if not td:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return _tool_to_dict(td)
