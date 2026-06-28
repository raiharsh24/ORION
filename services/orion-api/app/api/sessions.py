from fastapi import APIRouter, HTTPException
from typing import List
from app.models.schemas import SessionDetailResponse, MessageDetail
from app.core.dependencies import memory_store

router = APIRouter()

@router.get("/sessions", response_model=List[SessionDetailResponse])
async def get_all_sessions() -> List[SessionDetailResponse]:
    sessions = memory_store.list_sessions()
    result = []
    for s in sessions:
        msgs = [
            MessageDetail(role=m.role, content=m.content, timestamp=m.timestamp) 
            for m in s.messages
        ]
        result.append(
            SessionDetailResponse(
                session_id=s.session_id,
                messages=msgs,
                created_at=s.created_at,
                summary=s.summary,
                context=s.context,
                tool_used=s.tool_used,
                tool_output=s.tool_output
            )
        )
    return result

@router.get("/sessions/{id}", response_model=SessionDetailResponse)
async def get_session_by_id(id: str) -> SessionDetailResponse:
    s = memory_store.get_session(id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Session '{id}' not found.")
    
    msgs = [
        MessageDetail(role=m.role, content=m.content, timestamp=m.timestamp) 
        for m in s.messages
    ]
    return SessionDetailResponse(
        session_id=s.session_id,
        messages=msgs,
        created_at=s.created_at,
        summary=s.summary,
        context=s.context,
        tool_used=s.tool_used,
        tool_output=s.tool_output
    )
