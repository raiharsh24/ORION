import os
from typing import Dict, Any, List, Optional
from loguru import logger

from app.memory.schema import SessionMemory, ChatMessage
from app.memory.store import JSONStore, InMemoryStore
from app.memory.manager import MemoryManager
from app.memory.serializer import MemorySerializer

class MemoryEngine:
    """
    Main MemoryEngine service registered inside OrionServiceContainer.
    Implements Alpha 4.0 lifecycle hooks, health monitoring, and backwards-compatible wrappers.
    """
    def __init__(self) -> None:
        self._manager: Optional[MemoryManager] = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Lifecycle initialize hook. Bootstraps store, managers, and EventBus binds.
        """
        if self._initialized:
            return

        logger.info("Initializing MemoryEngine service...")
        from app.kernel.kernel import OrionKernel
        kernel = OrionKernel.get_instance()
        config = getattr(kernel, "_config", None)
        
        # Configure file persistence if dir is set
        if config and config.paths and config.paths.persist_dir:
            file_path = os.path.join(config.paths.persist_dir, "orion_memory.json")
            store = JSONStore(file_path)
        else:
            store = InMemoryStore()
            
        self._event_bus = kernel.get_service("event_bus")
        self._manager = MemoryManager(store=store, event_bus=self._event_bus)

        # Register EventBus subscribers
        if self._event_bus:
            self._event_bus.subscribe("ConversationCompleted", self._manager.on_conversation_completed)
            self._event_bus.subscribe("ToolCompleted", self._manager.on_tool_completed)
            self._event_bus.subscribe("MissionCompleted", self._manager.on_mission_completed)
            self._event_bus.subscribe("WorkflowCompleted", self._manager.on_workflow_completed)
            logger.info("MemoryEngine EventBus hook callbacks registered successfully.")

        self._initialized = True
        logger.info("MemoryEngine initialized successfully.")

    async def start(self) -> None:
        """Lifecycle start hook."""
        logger.info("MemoryEngine service started.")

    async def shutdown(self) -> None:
        """Lifecycle shutdown/persist hook."""
        logger.info("Shutting down MemoryEngine...")
        if self._event_bus and self._manager:
            self._event_bus.unsubscribe("ConversationCompleted", self._manager.on_conversation_completed)
            self._event_bus.unsubscribe("ToolCompleted", self._manager.on_tool_completed)
            self._event_bus.unsubscribe("MissionCompleted", self._manager.on_mission_completed)
            self._event_bus.unsubscribe("WorkflowCompleted", self._manager.on_workflow_completed)
        if self._manager and hasattr(self._manager._store, "save"):
            self._manager._store.save()
        self._initialized = False
        logger.info("MemoryEngine shut down successfully.")

    def health(self) -> Dict[str, Any]:
        """Exposes health metrics for the subsystem health monitor."""
        if not self._initialized or not self._manager:
            return {
                "status": "WARNING",
                "message": "Memory Engine is not initialized."
            }

        sessions_count = len([k for k in self._manager._store.keys() if k.startswith("session:")])
        projects_count = len([k for k in self._manager._store.keys() if k.startswith("project:")])
        avg_latency = 0.0
        if self._manager.retrieval_count > 0:
            avg_latency = self._manager.retrieval_latency_sum / self._manager.retrieval_count

        return {
            "status": "HEALTHY",
            "message": "Memory Engine v1.0 running nomially.",
            "details": {
                "session_count": sessions_count,
                "project_count": projects_count,
                "retrieval_latency_ms": round(avg_latency, 2),
                "errors_count": self._manager.errors_count
            }
        }

    # ==========================================
    # Backward Compatibility Mappings
    # ==========================================
    def get_or_create_session(self, session_id: str) -> SessionMemory:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        return self._manager.get_or_create_session(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        session = self.get_or_create_session(session_id)
        session.messages.append(ChatMessage(role=role, content=content))
        self._manager.save_session(session)

    def get_history_string(self, session_id: str) -> str:
        session = self.get_or_create_session(session_id)
        return "\n".join([f"{msg.role.capitalize()}: {msg.content}" for msg in session.messages])

    def update_summary(self, session_id: str, summary: str) -> None:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        session = self.get_or_create_session(session_id)
        session.summary = summary
        self._manager.save_session(session)

    def update_context(self, session_id: str, context: str) -> None:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        session = self.get_or_create_session(session_id)
        session.context = context
        self._manager.save_session(session)

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        key = f"session:{session_id}"
        data = self._manager._store.get(key)
        if data:
            return MemorySerializer.deserialize_session(data)
        return None

    def list_sessions(self) -> List[SessionMemory]:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        sessions = []
        for key in self._manager._store.keys():
            if key.startswith("session:"):
                data = self._manager._store.get(key)
                if data:
                    sessions.append(MemorySerializer.deserialize_session(data))
        return sessions

    def clear(self) -> None:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        self._manager._store.clear()
