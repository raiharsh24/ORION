from typing import Dict, Any, Optional
from loguru import logger

from app.kernel.registry import OrionServiceRegistry
from app.kernel.config import OrionKernelConfig
from app.kernel.context import OrionKernelContext, UserContext, MissionContext, WorkspaceContext, SystemMetadata
from app.kernel.state import KernelState

# Core Subsystem Imports
from app.events.bus import EventBus
from app.memory.conversation import ConversationMemory
from app.orion.vectordb import VectorDB
from app.memory.embeddings import EmbeddingsManager
from app.orion.retrieval import RetrievalEngine
from app.orion.planner import Planner
from app.desktop.controller import DesktopController
from app.missions.mission_manager import MissionManager, MissionTelemetry
from app.missions.mission_history import MissionHistory
from app.workflow.engine import WorkflowEngine
from app.workflow.history import WorkflowHistory
from app.scheduler.scheduler import OrionScheduler
from app.llm.router import LLMRouter
from app.llm.gemini import GeminiAdapter
from app.desktop.automation import DesktopAutomationService

class BootManager:
    """
    Orchestrates the sequential boot-up timeline of the ORION Kernel and core components.
    """
    def __init__(self, registry: OrionServiceRegistry) -> None:
        """Initialize the BootManager."""
        self._registry = registry

    async def run_boot_sequence(self, config: OrionKernelConfig) -> OrionKernelContext:
        """
        Executes the step-by-step service startup sequence.

        Args:
            config (OrionKernelConfig): Target configuration profiles.

        Returns:
            OrionKernelContext: Active context mapping running system states.
        """
        logger.info("Executing ORION BootManager sequence...")
        
        # Step 1: Load Configuration (Done by caller/passed in)
        logger.info("Boot Step 1: Load Configuration - SUCCESS")
        
        # Step 2: Initialize Logger
        logger.info("Boot Step 2: Initialize Logger - SUCCESS")
        
        # Step 3: Initialize Registry & Core Event Bus
        logger.info("Boot Step 3: Initialize Registry & Event Bus...")
        event_bus = EventBus()
        self._registry.register("event_bus", event_bus)
        logger.info("Event Bus registered in OrionServiceRegistry.")
        
        # Step 4: Initialize Memory
        logger.info("Boot Step 4: Initialize Memory...")
        memory_engine = ConversationMemory()
        self._registry.register("memory_engine", memory_engine)
        logger.info("Memory Engine registered in OrionServiceRegistry.")
        
        # Step 5: Initialize Knowledge
        logger.info("Boot Step 5: Initialize Knowledge...")
        try:
            vector_db = VectorDB(config.paths.persist_dir)
            embeddings = EmbeddingsManager()
            knowledge_engine = RetrievalEngine(vector_db, embeddings)
            self._registry.register("knowledge_engine", knowledge_engine)
            logger.info("Knowledge Engine (RetrievalEngine) registered in OrionServiceRegistry.")
        except Exception as e:
            logger.error(f"Failed to initialize Knowledge Engine: {str(e)}")
            raise e
            
        # Step 6: Initialize Planner
        logger.info("Boot Step 6: Initialize Planner...")
        planner = Planner()
        self._registry.register("planner", planner)
        logger.info("Planner registered in OrionServiceRegistry.")
        
        # Step 7: Initialize Desktop Controller
        logger.info("Boot Step 7: Initialize Desktop Controller...")
        desktop_controller = DesktopController()
        self._registry.register("desktop_controller", desktop_controller)
        logger.info("Desktop Controller registered in OrionServiceRegistry.")
        
        # Step 7b: Initialize Desktop Automation Service
        logger.info("Boot Step 7b: Initialize Desktop Automation Service...")
        desktop_automation = DesktopAutomationService()
        await desktop_automation.initialize()
        self._registry.register("desktop_automation", desktop_automation)
        logger.info("Desktop Automation Service registered in OrionServiceRegistry.")
        
        # Step 8: Initialize Mission Engine
        logger.info("Boot Step 8: Initialize Mission Engine...")
        telemetry = MissionTelemetry()
        self._registry.register("telemetry", telemetry)
        history = MissionHistory()
        mission_engine = MissionManager(
            event_bus=event_bus,
            telemetry=telemetry,
            history=history
        )
        self._registry.register("mission_engine", mission_engine)
        logger.info("Mission Engine (MissionManager) registered in OrionServiceRegistry.")
        
        # Step 9: Initialize Workflow Engine (full DI)
        logger.info("Boot Step 9: Initialize Workflow Engine...")
        workflow_history = WorkflowHistory()
        self._registry.register("workflow_history", workflow_history)
        workflow_engine = WorkflowEngine(
            mission_engine=mission_engine,
            desktop_automation=desktop_automation,
            desktop_controller=desktop_controller,
            knowledge_engine=knowledge_engine,
            planner=planner,
            event_bus=event_bus,
            history=workflow_history,
        )
        self._registry.register("workflow_engine", workflow_engine)
        logger.info("Workflow Engine (full) registered in OrionServiceRegistry.")
        
        # Step 10: Initialize Scheduler (Placeholder)
        logger.info("Boot Step 10: Initialize Scheduler (Placeholder)...")
        scheduler = OrionScheduler()
        self._registry.register("scheduler", scheduler)
        logger.info("Scheduler registered in OrionServiceRegistry.")
        
        # Additional: Initialize LLM Router
        logger.info("Boot Step 10b: Initialize LLM Router...")
        llm_router = LLMRouter()
        # Register default Gemini adapter
        gemini_adapter = GeminiAdapter(
            api_key=config.api_keys.gemini_api_key,
            model_name=config.models.default_llm
        )
        llm_router.register_provider("gemini", gemini_adapter, is_default=True)
        self._registry.register("llm_router", llm_router)
        logger.info("LLM Router registered in OrionServiceRegistry.")
        
        # Late-bind LLM Router into Workflow Engine
        workflow_engine._llm_router = llm_router
        logger.info("LLM Router late-bound into Workflow Engine.")
        
        # Construct Context
        user_ctx = UserContext()
        mission_ctx = MissionContext()
        workspace_ctx = WorkspaceContext(active_workspace_path=config.paths.workspace_root)
        metadata = SystemMetadata()
        
        context = OrionKernelContext(
            user=user_ctx,
            mission=mission_ctx,
            workspace=workspace_ctx,
            loaded_services=self._registry.list_services(),
            state=KernelState.READY,
            config=config,
            metadata=metadata
        )
        
        logger.info("Boot Step 11: Ready - Boot sequence completed successfully.")
        return context
