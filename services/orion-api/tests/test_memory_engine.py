import os
import pytest
import tempfile
import time
import anyio
from typing import Dict, Any

from app.memory.schema import (
    MemoryEntry, ChatMessage, WorkingMemory, SessionMemory, UserMemory, ProjectMemory
)
from app.memory.store import InMemoryStore, JSONStore
from app.memory.serializer import MemorySerializer
from app.memory.events import (
    MemoryCreated, MemoryUpdated, SessionSummarized, ProjectUpdated, UserPreferenceChanged
)
from app.memory.retriever import MemoryRetriever
from app.memory.manager import MemoryManager
from app.memory.engine import MemoryEngine
from app.events.bus import EventBus
from app.events.events import OrionEvent
from app.kernel import OrionKernel, OrionKernelConfig

# ----------------------------------------------------
# 1. Storage & Serialization Tests
# ----------------------------------------------------
def test_in_memory_store():
    store = InMemoryStore()
    assert store.get("key") is None
    store.put("key", "value")
    assert store.get("key") == "value"
    store.delete("key")
    assert store.get("key") is None

def test_json_store_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test_store.json")
        store = JSONStore(file_path)
        store.put("foo", "bar")
        store.put("hello", {"world": 123})
        
        # Instantiate second store to load persisted data
        store2 = JSONStore(file_path)
        assert store2.get("foo") == "bar"
        assert store2.get("hello") == {"world": 123}

def test_serializer_conversions():
    entry = MemoryEntry(content="test pref", category="preference", importance=8)
    data = MemorySerializer.serialize_entry(entry)
    parsed = MemorySerializer.deserialize_entry(data)
    assert parsed.id == entry.id
    assert parsed.content == "test pref"
    assert parsed.importance == 8

# ----------------------------------------------------
# 2. Ranking & Retrieval Tests
# ----------------------------------------------------
def test_retriever_ranking_logic():
    retriever = MemoryRetriever()
    now = time.time()
    
    # Low importance, old timestamp, query match
    e1 = MemoryEntry(content="favorite editor is vim", importance=3, timestamp=now - 50000)
    # High importance, recent timestamp, query match
    e2 = MemoryEntry(content="editor coding tool is vscode", importance=9, timestamp=now - 10)
    # High importance, recent timestamp, NO query match
    e3 = MemoryEntry(content="favorite food is pizza", importance=9, timestamp=now - 5)

    query_tokens = {"editor", "vscode"}
    
    score1 = retriever.calculate_score(e1, query_tokens, now)
    score2 = retriever.calculate_score(e2, query_tokens, now)
    score3 = retriever.calculate_score(e3, query_tokens, now)
    
    # vscode match (e2) should score highest due to match + recency + importance
    assert score2 > score1
    assert score2 > score3

def test_retriever_retrieve_normalization():
    retriever = MemoryRetriever()
    
    user_mem = UserMemory(user_id="alice", preferences={"coding_style": "spaces"})
    project_mem = ProjectMemory(project_id="orion", name="ORION")
    project_mem.decisions.append({"content": "use FastAPI for gateway routing", "importance": 8})
    session_mem = SessionMemory(session_id="session_123")
    session_mem.messages.append(ChatMessage(role="user", content="coding preferences query"))
    
    results = retriever.retrieve(
        query="coding routing preferences",
        user_memory=user_mem,
        project_memory=project_mem,
        session_memory=session_mem,
        limit=5
    )
    
    assert len(results) >= 3
    contents = [r.content for r in results]
    assert any("spaces" in c for c in contents)
    assert any("FastAPI" in c for c in contents)

# ----------------------------------------------------
# 3. Manager & EventBus Callback Tests
# ----------------------------------------------------
@pytest.mark.anyio
async def test_manager_events_interception():
    event_bus = EventBus()
    store = InMemoryStore()
    manager = MemoryManager(store=store, event_bus=event_bus)
    
    # Subscribe manager callbacks to EventBus
    event_bus.subscribe("ConversationCompleted", manager.on_conversation_completed)
    event_bus.subscribe("ToolCompleted", manager.on_tool_completed)
    event_bus.subscribe("MissionCompleted", manager.on_mission_completed)
    
    # 1. Test ConversationCompleted -> Session summary trigger
    session = manager.get_or_create_session("sess_xyz")
    session.messages.append(ChatMessage(role="user", content="hello"))
    session.messages.append(ChatMessage(role="assistant", content="hi"))
    manager.save_session(session)
    
    summarized_events = []
    event_bus.subscribe("SessionSummarized", lambda e: summarized_events.append(e))
    
    await event_bus.publish(OrionEvent("ConversationCompleted", {"session_id": "sess_xyz"}))
    await anyio.sleep(0.1)
    
    assert len(summarized_events) == 1
    assert "sess_xyz" in summarized_events[0].data["session_id"]
    updated_session = manager.get_or_create_session("sess_xyz")
    assert "Completed conversation" in updated_session.summary

    # 2. Test ToolCompleted -> working memory update
    await event_bus.publish(OrionEvent("ToolCompleted", {"tool_name": "filesystem", "output": "file list details", "session_id": "sess_xyz"}))
    await anyio.sleep(0.1)
    assert len(manager.get_working_memory().active_tool_results) == 1
    assert manager.get_working_memory().active_tool_results[0]["tool"] == "filesystem"

# ----------------------------------------------------
# 4. Engine Lifecycle & Backwards Compatibility Tests
# ----------------------------------------------------
@pytest.mark.anyio
async def test_engine_lifecycle_and_compatibility():
    OrionKernel.reset_instance()
    config = OrionKernelConfig()
    kernel = OrionKernel.get_instance(config)
    
    # Boot kernel to register core services
    await kernel.boot()
    
    engine = kernel.get_service("memory_engine")
    assert engine is not None
    assert isinstance(engine, MemoryEngine)
    
    # Test health monitor output
    h = engine.health()
    assert h["status"] == "HEALTHY"
    assert "session_count" in h["details"]
    
    # Test backward-compatible ConversationMemory methods
    engine.clear()
    session = engine.get_or_create_session("sess_999")
    assert session.session_id == "sess_999"
    
    engine.add_message("sess_999", "user", "Compatible query")
    engine.add_message("sess_999", "assistant", "Compatible response")
    
    hist = engine.get_history_string("sess_999")
    assert "User: Compatible query" in hist
    assert "Assistant: Compatible response" in hist
    
    engine.update_summary("sess_999", "custom summary")
    assert engine.get_session("sess_999").summary == "custom summary"
    
    engine.update_context("sess_999", "active-flow")
    assert engine.get_session("sess_999").context == "active-flow"
    
    sessions = engine.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "sess_999"
    
    # Shutdown sequence verification
    await kernel.shutdown()
