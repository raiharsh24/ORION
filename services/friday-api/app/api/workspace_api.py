from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.kernel.kernel import FridayKernel
from app.workspace.integration import WorkspaceContextProvider

router = APIRouter()


def _get_provider() -> WorkspaceContextProvider:
    kernel = FridayKernel.get_instance()
    provider = kernel.get_service("workspace_provider") if kernel else None
    if not provider:
        provider = WorkspaceContextProvider()
        if kernel:
            kernel._registry.register("workspace_provider", provider)
    return provider


@router.get("/workspace/projects")
async def list_projects(
    rescan: bool = Query(False, description="Force re-scan"),
) -> Dict[str, Any]:
    provider = _get_provider()
    projects = await provider.discover_projects(rescan=rescan)
    ctx = provider.get_workspace_context()
    return ctx


@router.get("/workspace/projects/{path:path}")
async def get_project(path: str) -> Dict[str, Any]:
    provider = _get_provider()
    norm = os.path.normpath("/" + path) if not path.startswith("/") else os.path.normpath(path)

    project = provider.get_project(norm)
    if not project:
        projects = await provider.discover_projects()
        project = provider.get_project(norm)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {norm}")

    graph = await provider.build_graph(norm)
    ctx = provider.get_project_context(norm)
    return ctx


@router.post("/workspace/scan")
async def trigger_scan(
    scan_path: Optional[str] = Query(None, description="Path to scan"),
) -> Dict[str, Any]:
    provider = _get_provider()
    projects = await provider.discover_projects(scan_path=scan_path, rescan=True)
    return {
        "success": True,
        "projects_discovered": len(projects),
        "project_names": [p.name for p in projects],
    }


@router.get("/workspace/health")
async def workspace_health() -> Dict[str, Any]:
    provider = _get_provider()
    return provider.health()


@router.get("/workspace/insights")
async def workspace_insights() -> Dict[str, Any]:
    provider = _get_provider()
    ctx = provider.get_workspace_context()
    insights: List[str] = []

    for proj in ctx.get("projects", []):
        stats = proj.get("graph_stats")
        if stats:
            if stats["total_files"] > 100:
                insights.append(
                    f"{proj['name']} has {stats['total_files']} files — "
                    "consider modularising."
                )
            if stats["entry_points"] == 0:
                insights.append(
                    f"{proj['name']} has no recognised entry point."
                )
        if proj.get("technologies"):
            insights.append(
                f"{proj['name']} uses {', '.join(proj['technologies'])}."
            )
        if proj.get("branch"):
            insights.append(
                f"{proj['name']} is on branch '{proj['branch']}'."
            )

    if not insights:
        insights.append("No workspace projects discovered yet.")

    return {
        "insights": insights,
        "insight_count": len(insights),
    }
