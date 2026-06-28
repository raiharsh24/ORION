from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.schemas import (
    KnowledgeIndexRequest, KnowledgeIndexResponse,
    KnowledgeSearchRequest, KnowledgeSearchResponse, KnowledgeSearchResultDetail,
    ProjectDetailResponse
)
from app.core.dependencies import workspace_manager, document_indexer, retrieval_engine

router = APIRouter()

@router.post("/knowledge/index", response_model=KnowledgeIndexResponse)
async def index_workspace(request: KnowledgeIndexRequest) -> KnowledgeIndexResponse:
    """
    Triggers indexing on a local file path.
    """
    path = request.path or workspace_manager.root_dir
    proj_name = request.project_name
    
    try:
        chunks_added = await document_indexer.index_directory(path, project_name=proj_name)
        proj_label = f" (Project: {proj_name})" if proj_name else ""
        return KnowledgeIndexResponse(
            success=True,
            indexed_chunks=chunks_added,
            message=f"Successfully indexed workspace path '{path}'{proj_label}. Generated {chunks_added} chunks."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to index workspace: {str(e)}")

@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    """
    Performs semantic search across all indexed chunks.
    """
    try:
        results = await retrieval_engine.search(request.query, n_results=request.n_results or 5)
        formatted_results = [
            KnowledgeSearchResultDetail(
                id=item["id"],
                document=item["document"],
                metadata=item["metadata"],
                score=item["score"]
            )
            for item in results
        ]
        return KnowledgeSearchResponse(
            success=True,
            results=formatted_results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge base: {str(e)}")

@router.get("/workspace/projects", response_model=List[ProjectDetailResponse])
async def get_projects() -> List[ProjectDetailResponse]:
    """
    Scans the workspace directory and lists discovered repositories and projects.
    """
    try:
        projects = workspace_manager.discover_projects()
        formatted_projects = [
            ProjectDetailResponse(
                name=p["name"],
                path=p["path"],
                is_git=p["is_git"],
                branch=p.get("branch"),
                files_count=p["files_count"],
                languages=p["languages"]
            )
            for p in projects
        ]
        return formatted_projects
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan workspace projects: {str(e)}")
