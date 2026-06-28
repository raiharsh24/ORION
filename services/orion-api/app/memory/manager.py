import time
from typing import Dict, Any, List, Optional
from loguru import logger

from app.memory.schema import (
    WorkingMemory, SessionMemory, UserMemory, ProjectMemory,
    MemoryEntry, ChatMessage
)
from app.memory.store import MemoryStore, InMemoryStore
from app.memory.serializer import MemorySerializer
from app.memory.retriever import MemoryRetriever
from app.memory.events import (
    MemoryCreated, MemoryUpdated, MemoryExpired,
    SessionSummarized, ProjectUpdated, UserPreferenceChanged,
    MemoryError, MemoryRetrieved
)
from app.events.events import OrionEvent

class MemoryManager:
    """
    Orchestrates the active layers of Working, Session, User, and Project memory.
    Saves state to a MemoryStore implementation, handles callback hooks for the EventBus,
    and coordinates ranking retrievals.
    """
    def __init__(self, store: Optional[MemoryStore] = None, event_bus: Optional[Any] = None) -> None:
        self._store = store or InMemoryStore()
        self._event_bus = event_bus
        self._retriever = MemoryRetriever()
        
        # Working memory is request/thread level, kept here for default queries
        self._working_memory = WorkingMemory()
        
        # Performance/Health metrics
        self.retrieval_latency_sum = 0.0
        self.retrieval_count = 0
        self.errors_count = 0

    def get_working_memory(self) -> WorkingMemory:
        return self._working_memory

    def get_or_create_session(self, session_id: str) -> SessionMemory:
        key = f"session:{session_id}"
        data = self._store.get(key)
        if data:
            try:
                return MemorySerializer.deserialize_session(data)
            except Exception as e:
                logger.error(f"Error parsing SessionMemory '{session_id}': {str(e)}")
                self.errors_count += 1
                
        # Initialize a new session
        session = SessionMemory(session_id=session_id)
        self.save_session(session)
        return session

    def save_session(self, session: SessionMemory) -> None:
        key = f"session:{session.session_id}"
        session.updated_at = time.time()
        self._store.put(key, MemorySerializer.serialize_session(session))

    def get_user_memory(self, user_id: str = "default_user") -> UserMemory:
        key = f"user:{user_id}"
        data = self._store.get(key)
        if data:
            try:
                return MemorySerializer.deserialize_user(data)
            except Exception as e:
                logger.error(f"Error parsing UserMemory '{user_id}': {str(e)}")
                self.errors_count += 1
                
        user = UserMemory(user_id=user_id)
        self.save_user_memory(user)
        return user

    def save_user_memory(self, user: UserMemory) -> None:
        key = f"user:{user.user_id}"
        user.updated_at = time.time()
        self._store.put(key, MemorySerializer.serialize_user(user))

    def get_project_memory(self, project_id: str) -> ProjectMemory:
        key = f"project:{project_id}"
        data = self._store.get(key)
        if data:
            try:
                return MemorySerializer.deserialize_project(data)
            except Exception as e:
                logger.error(f"Error parsing ProjectMemory '{project_id}': {str(e)}")
                self.errors_count += 1
                
        project = ProjectMemory(project_id=project_id, name=project_id)
        self.save_project_memory(project)
        return project

    def save_project_memory(self, project: ProjectMemory) -> None:
        key = f"project:{project.project_id}"
        project.updated_at = time.time()
        self._store.put(key, MemorySerializer.serialize_project(project))

    def _safe_publish(self, event: OrionEvent) -> None:
        if not self._event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self._event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    asyncio.run(self._event_bus.publish(event))
            else:
                self._event_bus.publish(event)
        except Exception as e:
            logger.error(f"Failed to publish event to EventBus: {str(e)}")

    def retrieve_relevant_context(
        self,
        query: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: str = "default_user",
        limit: int = 5
    ) -> List[MemoryEntry]:
        """
        Gathers memory objects from all memory layers and performs deterministic ranking.
        """
        start_time = time.time()
        user_mem = self.get_user_memory(user_id)
        proj_mem = self.get_project_memory(project_id) if project_id else None
        sess_mem = self.get_or_create_session(session_id) if session_id else None

        results = self._retriever.retrieve(
            query=query,
            user_memory=user_mem,
            project_memory=proj_mem,
            session_memory=sess_mem,
            limit=limit
        )

        latency = (time.time() - start_time) * 1000.0  # in ms
        self.retrieval_count += 1
        self.retrieval_latency_sum += latency

        # Publish retrieved event
        self._safe_publish(MemoryRetrieved(
            session_id=session_id or "global",
            query=query,
            results_count=len(results)
        ))
            
        return results

    # ==========================================
    # Event Listener Callback Subscription Hooks
    # ==========================================
    def on_conversation_completed(self, event: OrionEvent) -> None:
        """Invoked on ConversationCompleted. Auto-summarizes session."""
        session_id = event.data.get("session_id")
        if not session_id:
            return
            
        logger.info(f"MemoryManager intercepted ConversationCompleted event for session {session_id}.")
        session = self.get_or_create_session(session_id)
        
        # Calculate summary placeholder from message log length
        msg_count = len(session.messages)
        summary = f"Summary: Completed conversation with {msg_count} turns."
        session.summary = summary
        self.save_session(session)
        
        self._safe_publish(SessionSummarized(session_id=session_id, summary=summary))

    def on_tool_completed(self, event: OrionEvent) -> None:
        """Invoked on ToolCompleted. Records memory of tool outputs."""
        tool_name = event.data.get("tool_name")
        output = event.data.get("output", "")
        session_id = event.data.get("session_id") or "global"
        
        logger.info(f"MemoryManager intercepted ToolCompleted event for tool {tool_name}.")
        
        # Log to working memory reasoning / tool results
        self._working_memory.active_tool_results.append({
            "tool": tool_name,
            "output": str(output)[:200],  # Truncate for token efficiency
            "timestamp": time.time()
        })
        
        # Add to session history
        if session_id != "global":
            session = self.get_or_create_session(session_id)
            session.messages.append(
                ChatMessage(role="system", content=f"Tool '{tool_name}' executed. Result: {str(output)[:100]}")
            )
            self.save_session(session)

    def on_mission_completed(self, event: OrionEvent) -> None:
        """Invoked on MissionCompleted. Saves project memory status changes."""
        mission_id = event.data.get("mission_id")
        project_id = event.data.get("project_id") or "default_project"
        status = event.data.get("status", "COMPLETED")
        
        logger.info(f"MemoryManager intercepted MissionCompleted event: mission {mission_id}.")
        
        project = self.get_project_memory(project_id)
        # Update project milestones
        project.milestones[f"mission_{mission_id}"] = status
        self.save_project_memory(project)
        
        self._safe_publish(ProjectUpdated(project_id=project_id, data=project.model_dump()))

    def on_workflow_completed(self, event: OrionEvent) -> None:
        """Invoked on WorkflowCompleted."""
        workflow_id = event.data.get("workflow_id")
        logger.info(f"MemoryManager intercepted WorkflowCompleted: {workflow_id}.")
