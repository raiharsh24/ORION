"""
Universal Tool Registry discovery API.

Exposes the (now-activated) Universal Tool Registry for tool discovery,
metadata, health, and capability listing. Read-only; respects auth via the
global AuthMiddleware when FRIDAY_AUTH_DISABLED is False.

Route order matters: static paths (/tools/health, /tools/capabilities,
/tools/select) are declared BEFORE the parameterized /tools/{tool_id} so the
latter does not shadow them.
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


@router.get("/tools")
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Free-text search in name/description"),
) -> Dict[str, Any]:
    registry = _get_registry()
    tools = registry.list_metadata()
    if category:
        tools = [t for t in tools if t.category == category]
    if q:
        ql = q.lower()
        tools = [t for t in tools if ql in t.name.lower() or ql in t.description.lower()]
    return {
        "count": len(tools),
        "tools": [t.model_dump() if hasattr(t, "model_dump") else t for t in tools],
    }


@router.get("/tools/health")
async def tools_health() -> Dict[str, Any]:
    registry = _get_registry()
    health = registry.registry_health()
    return health.__dict__ if hasattr(health, "__dict__") else dict(health)


@router.get("/tools/capabilities")
async def tools_capabilities() -> Dict[str, Any]:
    """List capabilities resolved from the registered tools (discovery)."""
    registry = _get_registry()
    tools = registry.list_metadata()
    categories = sorted({t.category for t in tools})
    return {
        "total_tools": len(tools),
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
    }


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str) -> Dict[str, Any]:
    registry = _get_registry()
    meta = registry.get_metadata(tool_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    health = registry.get_tool_health(tool_id)
    permission = registry.get_permission(tool_id)
    return {
        "id": meta.id,
        "name": meta.name,
        "description": meta.description,
        "category": meta.category,
        "version": meta.version,
        "tags": meta.tags,
        "permission_level": permission.value if permission else None,
        "health": health.__dict__ if health else None,
    }
