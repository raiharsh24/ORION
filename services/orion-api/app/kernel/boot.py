from typing import Dict, Any, Optional
from loguru import logger

from app.kernel.container import OrionServiceContainer
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
from app.agents import (
    AgentMessageBus, AgentRegistry, AgentScheduler, AgentTelemetry,
    SharedContext, AgentCoordinator
)

class BootManager:
    """
    Orchestrates the sequential boot-up timeline of the ORION Kernel, registering
    subsystem modules, dependency container singletons, and capability catalogs.
    """
    def __init__(self, container: OrionServiceContainer) -> None:
        """Initialize the BootManager."""
        self._container = container

    async def run_boot_sequence(self, config: OrionKernelConfig) -> OrionKernelContext:
        """
        Executes step-by-step DI registration, capability indexing, and context creation.
        """
        logger.info("Executing ORION BootManager sequence...")
        from app.kernel.kernel import OrionKernel
        kernel = OrionKernel.get_instance()
        
        # Step 1: Load Configuration (Done by caller/passed in)
        logger.info("Boot Step 1: Load Configuration - SUCCESS")
        
        # Step 2: Initialize Logger
        logger.info("Boot Step 2: Initialize Logger - SUCCESS")
        
        # Step 3: Initialize Core Event Bus
        logger.info("Boot Step 3: Initialize Event Bus...")
        event_bus = EventBus()
        self._container.register_singleton("event_bus", event_bus)
        kernel.module_registry.register_module("event_bus", "1.0.0", [], event_bus)
        kernel.capability_registry.register_capability(
            name="PubSub",
            module_name="event_bus",
            description="System-wide decoupled prioritized message publishing and subscription broker"
        )
        logger.info("Event Bus registered in OrionServiceContainer.")
        
        # Step 4: Initialize Memory Engine
        logger.info("Boot Step 4: Initialize Memory Engine...")
        from app.core.dependencies import memory_store
        memory_engine = memory_store
        self._container.register_singleton("memory_engine", memory_engine)
        kernel.module_registry.register_module("memory_engine", "1.0.0", [], memory_engine)
        kernel.capability_registry.register_capability(
            name="Memory",
            module_name="memory_engine",
            description="Persistent and contextual Working, Session, User, and Project memory"
        )
        logger.info("Memory Engine registered in OrionServiceContainer.")
        
        # Step 5: Initialize Knowledge
        # Step 5: Initialize Knowledge Engine
        logger.info("Boot Step 5: Initialize Knowledge Engine...")
        try:
            from app.orion.knowledge_engine import KnowledgeEngine
            knowledge_engine = KnowledgeEngine()
            self._container.register_singleton("knowledge_engine", knowledge_engine)
            kernel.module_registry.register_module("knowledge_engine", "1.0.0", [], knowledge_engine)
            kernel.capability_registry.register_capability(
                name="Knowledge",
                module_name="knowledge_engine",
                description="Vector DB indexing and semantic search capabilities across local workspaces"
            )
            logger.info("Knowledge Engine registered in OrionServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Knowledge Engine: {str(e)}")
            raise e
            
        # Step 6: Initialize Planner Engine
        logger.info("Boot Step 6: Initialize Planner Engine...")
        planner = Planner()
        self._container.register_singleton("planner", planner)
        kernel.module_registry.register_module("planner", "1.0.0", [], planner)
        kernel.capability_registry.register_capability(
            name="Chat",
            module_name="planner",
            description="Production Intent, Goal, Capability, and Execution Planner"
        )
        logger.info("Planner Engine registered in OrionServiceContainer.")
        
        # Step 7: Initialize Desktop Controller
        logger.info("Boot Step 7: Initialize Desktop Controller...")
        from app.core.dependencies import desktop_controller, tool_registry
        self._container.register_singleton("desktop_controller", desktop_controller)
        self._container.register_singleton("tool_registry", tool_registry)
        kernel.module_registry.register_module("desktop_controller", "1.0.0", [], desktop_controller)
        kernel.capability_registry.register_capability(
            name="Desktop",
            module_name="desktop_controller",
            description="Direct control and automation capabilities over processes and operating system applications"
        )
        logger.info("Desktop Controller registered in OrionServiceContainer.")
        
        # Step 7b: Initialize Desktop Automation Service
        logger.info("Boot Step 7b: Initialize Desktop Automation Service...")
        desktop_automation = DesktopAutomationService()
        await desktop_automation.initialize()
        self._container.register_singleton("desktop_automation", desktop_automation)
        kernel.module_registry.register_module("desktop_automation", "1.0.0", [], desktop_automation)
        kernel.capability_registry.register_capability(
            name="Browser",
            module_name="desktop_automation",
            description="Headless browser navigation, text extraction, and form field filling"
        )
        logger.info("Desktop Automation Service registered in OrionServiceContainer.")
        
        # Step 7c: Initialize Tool Engine Subsystem
        logger.info("Boot Step 7c: Initialize Tool Engine...")
        from app.orion.tool_engine import ToolEngine
        tool_engine = ToolEngine()
        self._container.register_singleton("tool_engine", tool_engine)
        kernel.module_registry.register_module("tool_engine", "1.0.0", ["event_bus", "tool_registry"], tool_engine)
        logger.info("Tool Engine registered in OrionServiceContainer.")
        
        # Step 8: Initialize Mission Engine
        logger.info("Boot Step 8: Initialize Mission Engine...")
        telemetry = MissionTelemetry()
        self._container.register_singleton("telemetry", telemetry)
        history = MissionHistory()
        mission_engine = MissionManager(
            event_bus=event_bus,
            telemetry=telemetry,
            history=history,
            knowledge_engine=knowledge_engine
        )
        self._container.register_singleton("mission_engine", mission_engine)
        kernel.module_registry.register_module("mission_engine", "1.0.0", ["event_bus"], mission_engine)
        kernel.capability_registry.register_capability(
            name="Missions",
            module_name="mission_engine",
            description="Long-running user objective decomposition and step execution validation"
        )
        logger.info("Mission Engine (MissionManager) registered in OrionServiceContainer.")
        
        # Step 9: Initialize Workflow Engine (full DI)
        logger.info("Boot Step 9: Initialize Workflow Engine...")
        workflow_history = WorkflowHistory()
        self._container.register_singleton("workflow_history", workflow_history)
        workflow_engine = WorkflowEngine(
            mission_engine=mission_engine,
            desktop_automation=desktop_automation,
            desktop_controller=desktop_controller,
            knowledge_engine=knowledge_engine,
            planner=planner,
            event_bus=event_bus,
            history=workflow_history,
        )
        self._container.register_singleton("workflow_engine", workflow_engine)
        
        # Depends on all coordinate systems
        wf_deps = ["event_bus", "mission_engine", "desktop_automation", "desktop_controller", "knowledge_engine", "planner"]
        kernel.module_registry.register_module("workflow_engine", "1.0.0", wf_deps, workflow_engine)
        kernel.capability_registry.register_capability(
            name="Workflows",
            module_name="workflow_engine",
            description="Execution framework for parameterized templated workflows and macro actions"
        )
        logger.info("Workflow Engine (full) registered in OrionServiceContainer.")
        
        # Step 10: Initialize Scheduler
        logger.info("Boot Step 10: Initialize Scheduler (Placeholder)...")
        scheduler = OrionScheduler()
        self._container.register_singleton("scheduler", scheduler)
        kernel.module_registry.register_module("scheduler", "1.0.0", [], scheduler)
        kernel.capability_registry.register_capability(
            name="Calendar",
            module_name="scheduler",
            description="Time-based event triggers, cron actions scheduling, and notification alarms"
        )
        logger.info("Scheduler registered in OrionServiceContainer.")
        
        # Additional: Initialize LLM Router
        logger.info("Boot Step 10b: Initialize LLM Router...")
        llm_router = LLMRouter()
        gemini_adapter = GeminiAdapter(
            api_key=config.api_keys.gemini_api_key,
            model_name=config.models.default_llm
        )
        llm_router.register_provider("gemini", gemini_adapter, is_default=True)
        self._container.register_singleton("llm_router", llm_router)
        kernel.module_registry.register_module("llm_router", "1.0.0", [], llm_router)
        kernel.capability_registry.register_capability(
            name="Tools",
            module_name="llm_router",
            description="Provider-agnostic router matching and calling dynamic tool adapters"
        )
        logger.info("LLM Router registered in OrionServiceContainer.")
        
        # Late-bind LLM Router into Workflow Engine
        workflow_engine._llm_router = llm_router
        logger.info("LLM Router late-bound into Workflow Engine.")
        
        # Step 11: Initialize Multi-Agent Runtime (Alpha 4.5)
        logger.info("Boot Step 11: Initialize Multi-Agent Runtime...")
        try:
            agent_message_bus = AgentMessageBus(event_bus=event_bus)
            self._container.register_singleton("agent_message_bus", agent_message_bus)

            agent_registry = AgentRegistry(
                event_bus=event_bus,
                message_bus=agent_message_bus
            )
            self._container.register_singleton("agent_registry", agent_registry)

            agent_scheduler = AgentScheduler(event_bus=event_bus)
            self._container.register_singleton("agent_scheduler", agent_scheduler)

            agent_telemetry = AgentTelemetry(event_bus=event_bus)
            self._container.register_singleton("agent_telemetry", agent_telemetry)

            shared_context = SharedContext(kernel=kernel, event_bus=event_bus)
            self._container.register_singleton("shared_context", shared_context)

            agent_coordinator = AgentCoordinator(
                registry=agent_registry,
                message_bus=agent_message_bus,
                scheduler=agent_scheduler,
                telemetry=agent_telemetry,
                shared_context=shared_context,
                event_bus=event_bus
            )
            self._container.register_singleton("agent_coordinator", agent_coordinator)

            await agent_scheduler.start()

            kernel.capability_registry.register_capability(
                name="Agents",
                module_name="agent_coordinator",
                description="Multi-agent runtime with task routing, delegation, and parallel execution"
            )
            kernel.module_registry.register_module(
                "agent_coordinator", "1.0.0",
                ["event_bus", "memory_engine", "knowledge_engine", "planner"],
                agent_coordinator
            )
            logger.info("Multi-Agent Runtime registered in OrionServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Multi-Agent Runtime: {str(e)}")
            raise e

        # Step 12: Initialize Workflow Runtime (Alpha 5.0)
        logger.info("Boot Step 12: Initialize Workflow Runtime...")
        try:
            from app.workflow_runtime.persistence import WorkflowPersistence
            from app.workflow_runtime.checkpoints import CheckpointManager
            from app.workflow_runtime.worker_agent import WorkflowWorkerAgent
            from app.workflow_runtime.executor import WorkflowRuntimeExecutor
            from app.workflow_runtime.manager import WorkflowRuntimeManager
            from app.workflow_runtime.scheduler_bridge import RuntimeSchedulerBridge

            persist_dir = getattr(config.paths, "persist_dir", getattr(config.paths, "workspace_root", "./data"))
            workflow_persistence = WorkflowPersistence(persist_dir=persist_dir)
            self._container.register_singleton("workflow_persistence", workflow_persistence)

            checkpoint_manager = CheckpointManager(persist_dir=persist_dir)
            self._container.register_singleton("checkpoint_manager", checkpoint_manager)

            workflow_worker = WorkflowWorkerAgent(
                agent_id="workflow-worker",
                name="Workflow Worker",
                shared_context=shared_context
            )
            await agent_registry.register(workflow_worker)
            self._container.register_singleton("workflow_worker_agent", workflow_worker)

            runtime_executor = WorkflowRuntimeExecutor(
                agent_coordinator=agent_coordinator,
                shared_context=shared_context,
                checkpoint_manager=checkpoint_manager,
                event_bus=event_bus,
            )
            self._container.register_singleton("workflow_runtime_executor", runtime_executor)

            runtime_manager = WorkflowRuntimeManager(
                persistence=workflow_persistence,
                executor=runtime_executor,
                event_bus=event_bus,
            )
            self._container.register_singleton("workflow_runtime_manager", runtime_manager)

            scheduler_bridge = RuntimeSchedulerBridge(
                workflow_manager=runtime_manager,
                agent_scheduler=agent_scheduler,
            )
            self._container.register_singleton("runtime_scheduler_bridge", scheduler_bridge)

            kernel.module_registry.register_module(
                "workflow_runtime", "1.0.0",
                ["event_bus", "agent_coordinator", "shared_context", "scheduler"],
                runtime_manager
            )
            kernel.capability_registry.register_capability(
                name="WorkflowRuntime",
                module_name="workflow_runtime",
                description="Alpha 5.0 autonomous workflow runtime with step execution, checkpoints, and recovery"
            )
            logger.info("Workflow Runtime registered in OrionServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Workflow Runtime: {str(e)}")
            raise e

        # Construct Context
        user_ctx = UserContext()
        mission_ctx = MissionContext()
        workspace_ctx = WorkspaceContext(active_workspace_path=config.paths.workspace_root)
        metadata = SystemMetadata()
        
        context = OrionKernelContext(
            user=user_ctx,
            mission=mission_ctx,
            workspace=workspace_ctx,
            loaded_services=self._container.list_services(),
            state=KernelState.READY,
            config=config,
            metadata=metadata
        )
        
        logger.info("Boot Step 12: Ready - Boot sequence completed successfully.")
        return context
