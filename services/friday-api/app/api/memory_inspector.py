from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from loguru import logger

from app.memory import MemoryEngine
from app.memory.schema import MemoryEntry
from app.memory.serializer import MemorySerializer
from app.memory.graph import KnowledgeGraph, Entity
from app.memory.learning import LearningEngine
from app.memory.episodic import EpisodicMemory
from app.memory.store import InMemoryStore

router = APIRouter()


def _get_memory_engine() -> MemoryEngine:
    from app.kernel.kernel import FridayKernel
    kernel = FridayKernel.get_instance()
    engine = kernel.get_service("memory_engine") if kernel else None
    if not engine:
        raise HTTPException(status_code=503, detail="MemoryEngine not available")
    return engine


def _get_graph() -> KnowledgeGraph:
    try:
        engine = _get_memory_engine()
        if engine._manager and engine._manager._store:
            return KnowledgeGraph(store=engine._manager._store)
    except HTTPException:
        pass
    return KnowledgeGraph()


def _get_learning() -> LearningEngine:
    try:
        engine = _get_memory_engine()
        if engine._manager and engine._manager._store:
            return LearningEngine(store=engine._manager._store)
    except HTTPException:
        pass
    return LearningEngine()


def _get_episodic() -> EpisodicMemory:
    try:
        engine = _get_memory_engine()
        if engine._manager and engine._manager._store:
            return EpisodicMemory(store=engine._manager._store)
    except HTTPException:
        pass
    return EpisodicMemory()


@router.get("/memory/stats")
async def memory_stats() -> Dict[str, Any]:
    """Aggregate memory statistics across all layers."""
    engine = _get_memory_engine()
    if not engine._manager:
        raise HTTPException(status_code=503, detail="MemoryManager not available")

    store = engine._manager._store
    keys = store.keys()

    sessions = [k for k in keys if k.startswith("session:")]
    users = [k for k in keys if k.startswith("user:")]
    projects = [k for k in keys if k.startswith("project:")]
    episodic = [k for k in keys if k.startswith("episodic:")]
    consolidated = [k for k in keys if k.startswith("consolidated:")]
    learning = [k for k in keys if k.startswith("learning:")]
    graph_entities = [k for k in keys if k.startswith("graph:entity:")]
    graph_relations = [k for k in keys if k.startswith("graph:relation:")]

    learning_engine = _get_learning()
    graph = _get_graph()
    consolidator = getattr(engine, "_consolidator", None)

    total_messages = 0
    for sk in sessions:
        data = store.get(sk)
        if data:
            try:
                sess = MemorySerializer.deserialize_session(data)
                total_messages += len(sess.messages)
            except Exception:
                pass

    return {
        "total_keys": len(keys),
        "session_count": len(sessions),
        "user_count": len(users),
        "project_count": len(projects),
        "episodic_entries": len(episodic),
        "consolidated_entries": len(consolidated),
        "learning_patterns": len(learning),
        "graph_entities": len(graph_entities),
        "graph_relations": len(graph_relations),
        "total_messages_all_sessions": total_messages,
        "learning_stats": learning_engine.get_stats(),
        "graph_stats": graph.get_stats(),
        "consolidator_stats": consolidator.health() if consolidator else {"status": "NOT_CONFIGURED"},
        "retrieval_latency_ms": round(
            engine._manager.retrieval_latency_sum / max(engine._manager.retrieval_count, 1), 2
        ),
        "errors_count": engine._manager.errors_count,
    }


@router.get("/memory/entities")
async def memory_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    name_contains: Optional[str] = Query(None, description="Filter by name substring"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Query knowledge graph entities."""
    graph = _get_graph()
    return graph.query(entity_type=entity_type, name_contains=name_contains, limit=limit)


@router.get("/memory/entities/{entity_id}")
async def memory_entity_detail(entity_id: str) -> Dict[str, Any]:
    """Get a single entity with its relations."""
    graph = _get_graph()
    entity = graph.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    relations = graph.get_relations(entity_id)
    return {
        "entity": {
            "id": entity.id,
            "type": entity.type,
            "name": entity.name,
            "properties": entity.properties,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        },
        "relations": [
            {
                "source_id": r.source_id,
                "target_id": r.target_id,
                "type": r.type,
                "properties": r.properties,
                "created_at": r.created_at,
            }
            for r in relations
        ],
    }


@router.get("/memory/search")
async def memory_search(
    q: str = Query(..., min_length=1, description="Search query"),
    session_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    user_id: str = Query("default_user"),
    limit: int = Query(10, ge=1, le=50),
) -> Dict[str, Any]:
    """Semantic search across all memory layers."""
    engine = _get_memory_engine()
    if not engine._manager:
        raise HTTPException(status_code=503, detail="MemoryManager not available")

    results = engine._manager.retrieve_relevant_context(
        query=q,
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
        limit=limit,
    )

    return {
        "query": q,
        "results_count": len(results),
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "timestamp": r.timestamp,
                "metadata": r.metadata,
            }
            for r in results
        ],
    }


@router.get("/memory/conversations")
async def memory_conversations(
    limit: int = Query(20, ge=1, le=100),
    session_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """List conversation sessions with summaries."""
    engine = _get_memory_engine()
    if not engine._manager:
        raise HTTPException(status_code=503, detail="MemoryManager not available")

    store = engine._manager._store
    sessions = []

    for key in store.keys():
        if not key.startswith("session:"):
            continue
        if session_id and key != f"session:{session_id}":
            continue
        data = store.get(key)
        if not data:
            continue
        try:
            sess = MemorySerializer.deserialize_session(data)
            sessions.append({
                "session_id": sess.session_id,
                "message_count": len(sess.messages),
                "summary": sess.summary,
                "context": sess.context,
                "tool_used": sess.tool_used,
                "created_at": sess.created_at,
                "updated_at": sess.updated_at,
                "metadata": sess.metadata,
            })
        except Exception:
            continue

    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return {
        "total_sessions": len(sessions),
        "sessions": sessions[:limit],
    }


@router.get("/memory/conversations/{session_id}")
async def memory_conversation_detail(session_id: str) -> Dict[str, Any]:
    """Get full conversation history for a session."""
    engine = _get_memory_engine()
    if not engine._manager:
        raise HTTPException(status_code=503, detail="MemoryManager not available")

    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return {
        "session_id": session.session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
            }
            for m in session.messages
        ],
        "summary": session.summary,
        "context": session.context,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "metadata": session.metadata,
    }


@router.get("/memory/knowledge")
async def memory_knowledge(
    q: str = Query(..., min_length=1, description="Knowledge query"),
    n_results: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    """Query the vector knowledge base."""
    try:
        from app.friday.knowledge_engine import KnowledgeEngine

        engine = KnowledgeEngine()
        if not engine._initialized:
            await engine.initialize()
        results = await engine.search(q, n_results=n_results)
        return {
            "query": q,
            "results_count": len(results),
            "results": [
                {
                    "id": r["id"],
                    "document": r["document"],
                    "metadata": r["metadata"],
                    "score": r["score"],
                }
                for r in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"KnowledgeEngine query failed: {str(e)}")


@router.get("/memory/learning")
async def memory_learning(
    learning_type: Optional[str] = Query(None, description="Filter by learning type"),
    query: str = Query("", description="Search within learnings"),
    limit: int = Query(10, ge=1, le=50),
) -> Dict[str, Any]:
    """Query stored learning patterns."""
    learning = _get_learning()
    results = learning.get_relevant_learnings(
        query=query, learning_type=learning_type, limit=limit
    )
    return {
        "learning_type": learning_type,
        "results_count": len(results),
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "importance": r.importance,
                "category": r.category,
                "timestamp": r.timestamp,
                "metadata": r.metadata,
            }
            for r in results
        ],
        "tool_effectiveness": learning.get_tool_effectiveness(),
    }


@router.get("/memory/episodic")
async def memory_episodic(
    type_: str = Query("all", alias="type", description="Filter: mission, tool, workflow, or all"),
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    """Query episodic memory history."""
    episodic = _get_episodic()
    if type_ == "all":
        results = episodic.query_recent(limit=limit)
    elif type_ in ("mission", "tool", "workflow"):
        results = episodic.query_by_type(type_, limit=limit)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid type '{type_}'. Use: mission, tool, workflow, all")

    return {
        "type": type_,
        "results_count": len(results),
        "results": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "importance": r.importance,
                "timestamp": r.timestamp,
                "metadata": r.metadata,
            }
            for r in results
        ],
    }
