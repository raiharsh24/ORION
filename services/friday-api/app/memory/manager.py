import time
import hashlib
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
    MemoryError, MemoryRetrieved, MemoryCleanupCompleted,
)
from app.events.events import FridayEvent

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
        self._safe_publish(MemoryUpdated(
            memory_id=session.session_id, category="session",
            data={"session_id": session.session_id, "message_count": len(session.messages)}
        ))

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

    def _safe_publish(self, event: FridayEvent) -> None:
        if not self._event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self._event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    self._event_bus.publish_background(event)
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
        Includes mission/project/preference affinity scoring.
        """
        start_time = time.time()
        user_mem = self.get_user_memory(user_id)
        proj_mem = self.get_project_memory(project_id) if project_id else None
        sess_mem = self.get_or_create_session(session_id) if session_id else None

        affinity_context = {"user_id": user_id}
        if project_id:
            affinity_context["project_id"] = project_id
        if session_id:
            affinity_context["session_id"] = session_id

        results = self._retriever.retrieve(
            query=query,
            user_memory=user_mem,
            project_memory=proj_mem,
            session_memory=sess_mem,
            limit=limit,
            affinity_context=affinity_context,
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
    # Cleanup & Maintenance
    # ==========================================
    def run_cleanup(
        self,
        ttl_days: int = 30,
        min_importance: int = 3,
        max_session_messages: int = 500,
    ) -> Dict[str, int]:
        """Runs TTL expiration, session truncation, and deduplication.

        Returns a dict of cleanup counts.
        """
        now = time.time()
        ttl_seconds = ttl_days * 86400
        expired = 0
        truncated = 0
        deduped = 0
        consolidated = 0

        for key in list(self._store.keys()):
            # TTL-based expiration for consolidated/preference entries
            if key.startswith("consolidated:") or key.startswith("learning:"):
                data = self._store.get(key)
                if not data:
                    continue
                try:
                    entry = MemorySerializer.deserialize_entry(data)
                except Exception:
                    continue
                age = now - entry.timestamp
                if age > ttl_seconds:
                    self._store.delete(key)
                    expired += 1
                elif entry.expiration and entry.expiration < now:
                    self._store.delete(key)
                    expired += 1

            # Session message truncation
            if key.startswith("session:"):
                data = self._store.get(key)
                if not data:
                    continue
                try:
                    session = MemorySerializer.deserialize_session(data)
                except Exception:
                    continue

                if len(session.messages) > max_session_messages:
                    kept = session.messages[-max_session_messages:]
                    # Summarize the dropped portion
                    dropped = session.messages[:-max_session_messages]
                    if dropped:
                        session.summary = (
                            f"{session.summary or ''} "
                            f"[Previous {len(dropped)} messages summarized]"
                        ).strip()
                    session.messages = kept
                    self.save_session(session)
                    truncated += 1

                # Summarize sessions without summaries
                if not session.summary or session.summary == "Conversation session initialized.":
                    if len(session.messages) >= 4:
                        user_msgs = sum(1 for m in session.messages if m.role == "user")
                        asst_msgs = sum(1 for m in session.messages if m.role == "assistant")
                        last_topic = ""
                        for m in reversed(session.messages):
                            if m.role == "user":
                                last_topic = m.content[:100]
                                break
                        session.summary = (
                            f"Summary: {len(session.messages)} messages "
                            f"({user_msgs} user, {asst_msgs} assistant). "
                            f"Last user topic: {last_topic}."
                        )
                        self.save_session(session)
                        consolidated += 1

        # Deduplication within the same store prefix
        seen_hashes: Dict[str, str] = {}
        for key in list(self._store.keys()):
            if key.startswith("consolidated:preference:"):
                data = self._store.get(key)
                if not data:
                    continue
                content_str = str(data.get("content", ""))[:100]
                content_hash = hashlib.md5(content_str.encode()).hexdigest()
                if content_hash in seen_hashes:
                    self._store.delete(key)
                    deduped += 1
                else:
                    seen_hashes[content_hash] = key

        self._safe_publish(MemoryCleanupCompleted(
            expired=expired,
            truncated=truncated,
            consolidated=consolidated,
            deduped=deduped,
        ))

        logger.info(
            f"MemoryCleanup: {expired} expired, {truncated} truncated, "
            f"{consolidated} consolidated, {deduped} deduplicated"
        )
        return {
            "expired": expired,
            "truncated": truncated,
            "consolidated": consolidated,
            "deduped": deduped,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Returns storage statistics across all memory layers."""
        keys = self._store.keys()
        return {
            "total_keys": len(keys),
            "sessions": len([k for k in keys if k.startswith("session:")]),
            "users": len([k for k in keys if k.startswith("user:")]),
            "projects": len([k for k in keys if k.startswith("project:")]),
            "episodic": len([k for k in keys if k.startswith("episodic:")]),
            "consolidated": len([k for k in keys if k.startswith("consolidated:")]),
            "learning": len([k for k in keys if k.startswith("learning:")]),
            "graph_entities": len([k for k in keys if k.startswith("graph:entity:")]),
            "graph_relations": len([k for k in keys if k.startswith("graph:relation:")]),
            "retrieval_count": self.retrieval_count,
            "retrieval_latency_ms": round(
                self.retrieval_latency_sum / max(self.retrieval_count, 1), 2
            ),
            "errors_count": self.errors_count,
        }

    # ==========================================
    # Event Listener Callback Subscription Hooks
    # ==========================================
    def on_conversation_completed(self, event: FridayEvent) -> None:
        """Invoked on ConversationCompleted. Auto-summarizes session."""
        session_id = event.data.get("session_id")
        if not session_id:
            return
            
        logger.info(f"MemoryManager intercepted ConversationCompleted event for session {session_id}.")
        session = self.get_or_create_session(session_id)
        
        # Generate contextual summary
        msg_count = len(session.messages)
        user_msgs = sum(1 for m in session.messages if m.role == "user")
        asst_msgs = sum(1 for m in session.messages if m.role == "assistant")
        last_user_topic = ""
        for m in reversed(session.messages):
            if m.role == "user":
                last_user_topic = m.content[:150]
                break
        
        summary = (
            f"Summary: Completed conversation with {msg_count} turns "
            f"({user_msgs} user, {asst_msgs} assistant). "
            f"Last user topic: {last_user_topic}."
        )
        session.summary = summary
        self.save_session(session)
        
        self._safe_publish(SessionSummarized(session_id=session_id, summary=summary))

    def on_tool_completed(self, event: FridayEvent) -> None:
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

    def on_mission_completed(self, event: FridayEvent) -> None:
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

    def on_workflow_completed(self, event: FridayEvent) -> None:
        """Invoked on WorkflowCompleted."""
        workflow_id = event.data.get("workflow_id")
        logger.info(f"MemoryManager intercepted WorkflowCompleted: {workflow_id}.")
