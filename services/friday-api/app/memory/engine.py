import os
from typing import Dict, Any, List, Optional
from loguru import logger

from app.memory.schema import SessionMemory, ChatMessage
from app.memory.store import JSONStore, InMemoryStore, SQLiteStore
from app.memory.manager import MemoryManager
from app.memory.serializer import MemorySerializer
from app.memory.episodic import EpisodicMemory
from app.memory.graph import KnowledgeGraph
from app.memory.learning import LearningEngine
from app.memory.consolidator import MemoryConsolidator

class MemoryEngine:
    """
    Main MemoryEngine service registered inside FridayServiceContainer.
    Integrates MemoryManager, EpisodicMemory, KnowledgeGraph, LearningEngine,
    and MemoryConsolidator into a unified hierarchy.
    """
    def __init__(self) -> None:
        self._manager: Optional[MemoryManager] = None
        self._episodic: Optional[EpisodicMemory] = None
        self._graph: Optional[KnowledgeGraph] = None
        self._learning: Optional[LearningEngine] = None
        self._consolidator: Optional[MemoryConsolidator] = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Lifecycle initialize hook. Bootstraps store, managers, and EventBus binds.
        """
        if self._initialized:
            return

        logger.info("Initializing MemoryEngine service...")
        from app.kernel.kernel import FridayKernel
        kernel = FridayKernel.get_instance()
        config = getattr(kernel, "_config", None)
        
        # Configure file/DB persistence if dir is set
        if config and config.paths and config.paths.persist_dir:
            json_path = os.path.join(config.paths.persist_dir, "friday_memory.json")
            db_path = os.path.join(config.paths.persist_dir, "friday_memory.db")
            
            use_sqlite = os.getenv("FRIDAY_USE_SQLITE", "true").lower() == "true"
            
            if use_sqlite:
                try:
                    logger.info("Initializing SQLiteStore persistence backend...")
                    store = SQLiteStore(db_path)
                    
                    # Idempotent migration check: if JSON exists and SQLite is empty, migrate
                    if os.path.exists(json_path) and not store.keys():
                        logger.info("SQLiteStore is empty; starting migration from existing JSON memory file...")
                        try:
                            json_store = JSONStore(json_path)
                            for k in json_store.keys():
                                val = json_store.get(k)
                                if val is not None:
                                    store.put(k, val)
                            logger.info(f"Migration successful: copied {len(json_store.keys())} keys to SQLiteStore.")
                        except Exception as migration_err:
                            logger.error(f"Migration from JSON to SQLite failed: {migration_err}. Proceeding with SQLiteStore.")
                except Exception as db_err:
                    logger.error(f"SQLiteStore initialization failed: {db_err}. Falling back to JSONStore.")
                    store = JSONStore(json_path)
            else:
                logger.info("SQLiteStore disabled via environment flag. Initializing JSONStore backend.")
                store = JSONStore(json_path)
        else:
            store = InMemoryStore()
            
        self._event_bus = kernel.get_service("event_bus")
        self._manager = MemoryManager(store=store, event_bus=self._event_bus)

        # Initialize intelligence sub-components sharing the same store
        self._episodic = EpisodicMemory(store=store)
        self._graph = KnowledgeGraph(store=store)
        self._learning = LearningEngine(store=store, event_bus=self._event_bus)
        self._consolidator = MemoryConsolidator(manager=self._manager)

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
        if self._consolidator:
            await self._consolidator.start(interval_seconds=3600)
        logger.info("MemoryEngine service started.")

    async def shutdown(self) -> None:
        """Lifecycle shutdown/persist hook."""
        logger.info("Shutting down MemoryEngine...")
        if self._consolidator:
            await self._consolidator.stop()
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

        consolidator_health = self._consolidator.health() if self._consolidator else {"status": "NOT_CONFIGURED"}
        learning_stats = self._learning.get_stats() if self._learning else {}
        graph_stats = self._graph.get_stats() if self._graph else {}

        return {
            "status": "HEALTHY",
            "message": "Memory Engine v2.0 with intelligence subsystems.",
            "details": {
                "session_count": sessions_count,
                "project_count": projects_count,
                "retrieval_latency_ms": round(avg_latency, 2),
                "errors_count": self._manager.errors_count,
                "consolidator": consolidator_health,
                "learning": learning_stats,
                "knowledge_graph": graph_stats,
            }
        }

    # ==========================================
    # Intelligence Subsystem Accessors
    # ==========================================
    @property
    def episodic(self) -> EpisodicMemory:
        if not self._episodic:
            raise RuntimeError("MemoryEngine not initialized.")
        return self._episodic

    @property
    def graph(self) -> KnowledgeGraph:
        if not self._graph:
            raise RuntimeError("MemoryEngine not initialized.")
        return self._graph

    @property
    def learning(self) -> LearningEngine:
        if not self._learning:
            raise RuntimeError("MemoryEngine not initialized.")
        return self._learning

    @property
    def consolidator(self) -> MemoryConsolidator:
        if not self._consolidator:
            raise RuntimeError("MemoryEngine not initialized.")
        return self._consolidator

    @property
    def manager(self) -> MemoryManager:
        if not self._manager:
            raise RuntimeError("MemoryEngine not initialized.")
        return self._manager

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

    def run_cleanup(self, **kwargs) -> Dict[str, int]:
        if not self._manager:
            raise RuntimeError("MemoryEngine is not initialized.")
        return self._manager.run_cleanup(**kwargs)
