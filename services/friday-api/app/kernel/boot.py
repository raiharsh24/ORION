from typing import Dict, Any, List, Optional

from app.tools.base_tool import BaseTool
from loguru import logger

from app.kernel.container import FridayServiceContainer
from app.kernel.config import FridayKernelConfig
from app.kernel.context import FridayKernelContext, UserContext, MissionContext, WorkspaceContext, SystemMetadata
from app.kernel.state import KernelState

# Core Subsystem Imports
from app.events.bus import EventBus
from app.friday.planner import Planner
from app.friday.knowledge_engine import KnowledgeEngine
from app.friday.tool_engine import ToolEngine
from app.desktop.automation import DesktopAutomationService

# Milestone 5 Desktop Intelligence
from app.desktop_intelligence.service import DesktopIntelligence
from app.desktop_intelligence.middleware import DesktopContextMiddleware
from app.desktop_intelligence.extractor import DesktopIntelligenceExtractor
from app.missions.mission_manager import MissionManager, MissionTelemetry
from app.missions.mission_history import MissionHistory
from app.workflow.engine import WorkflowEngine
from app.workflow.history import WorkflowHistory
from app.scheduler.scheduler import FridayScheduler
from app.llm.router import LLMRouter
from app.llm.gemini import GeminiAdapter
from app.agents import (
    AgentMessageBus, AgentRegistry, AgentScheduler, AgentTelemetry,
    SharedContext, AgentCoordinator
)

# Phase 3 Intelligence Services
from app.intent.analyzer import RuleBasedIntentAnalyzer
from app.context.manager import StrategyManager
from app.extraction.registry import ExtractorRegistry
from app.extraction.extractors import (
    MemoryExtractor, KnowledgeExtractor, WorkflowExtractor,
    DesktopExtractor, BrowserExtractor, TerminalExtractor,
    MissionExtractor, VoiceExtractor, SystemStateExtractor,
)
from app.ranking.ranker import ContextRanker
from app.budget.allocator import AdaptiveTokenBudgetAllocator
from app.validation.validator import ContextValidator
from app.compression.compressor import ContextCompressor
from app.assembly.assembler import PromptAssembler

# Phase 5 Intelligence Pipeline
from app.intelligence.pipeline import IntelligencePipeline
from app.cache.cache import ContextCache

# Core dependencies
from app.core.dependencies import memory_store, desktop_controller as core_desktop_controller, tool_registry as core_tool_registry

# Phase 6 Universal Tool Registry
from app.tools.registry import ToolRegistry as UniversalToolRegistry
from app.tool_selection.selector import ToolSelectionEngine
from app.tool_execution.executor import ToolExecutionEngine
from app.workflow_engine.executor import WorkflowExecutor as WorkflowEngineV2
from app.mission_engine.executor import MissionExecutor
from app.mission_engine.mission import MissionStore
from app.mission_engine.checkpoint import CheckpointManager as MissionCheckpointManager
from app.mission_engine.planner import MissionPlanner
from app.capabilities.registry import CapabilityRegistry as CapabilityRegistryV2
from app.capabilities.resolver import CapabilityResolver
from app.capabilities.defaults import DEFAULT_CAPABILITIES

# Phase 7 Plugin SDK
from app.plugins.registry import PluginRegistry as Phase7PluginRegistry
from app.plugins.loader import PluginLoader as Phase7PluginLoader
from app.plugins.permissions import PermissionValidator as Phase7PermissionValidator
from app.plugin_runtime.runtime import PluginRuntime
from app.plugin_runtime.base import PluginRuntimeConfig
from app.plugin_marketplace.manager import PackageManager
from app.plugin_marketplace.base import MarketplaceConfig
from app.plugin_security.signature import PluginSigner
from app.plugin_security.trust_store import TrustStore
from app.plugin_security.publisher import PublisherRegistry
from app.plugin_security.repository_policy import RepositoryPolicyManager
from app.plugin_security.integrity import IntegrityVerifier
from app.plugin_security.verification import PluginVerifier
from app.plugin_security.update_policy import UpdatePolicy

# Phase 8 Agent Framework
from app.agent_framework.manager import AgentManager
from app.agent_framework.agent import create_all_builtin_agents
from app.agent_framework.locks import KeyLockManager
from app.agent_framework.blackboard import Blackboard
from app.agent_framework.delegation import DelegationManager
from app.agent_framework.coordinator import Coordinator
from app.agent_framework.priority import PriorityEngine
from app.agent_framework.consensus import ConsensusEngine
from app.agent_framework.persistence import PersistenceManager
from app.agent_framework.recovery import RecoveryManager
from app.agent_framework.metrics import MetricsCollector

# Phase 8 Cognitive Planning
from app.planning.planner import PlanningEngine

# Phase 9 Mission Runtime
from app.runtime.runtime import MissionRuntime

# Cognitive Core (Milestone 2 — Unified Planner, Knowledge Graph, Orchestration Facade)
from app.cognitive_core.core import CognitiveCore

# Alpha 5.0 Workflow Runtime
from app.workflow_runtime.persistence import WorkflowPersistence
from app.workflow_runtime.checkpoints import CheckpointManager as WorkflowCheckpointManager
from app.workflow_runtime.worker_agent import WorkflowWorkerAgent
from app.workflow_runtime.executor import WorkflowRuntimeExecutor
from app.workflow_runtime.manager import WorkflowRuntimeManager
from app.workflow_runtime.scheduler_bridge import RuntimeSchedulerBridge

# Voice Subsystem
from app.voice.manager import VoiceSessionManager
from app.voice.stt import GeminiSpeechProvider
from app.voice.state import VoiceStateMachine
from app.voice.tts import TTSProviderRegistry, MockTTSProvider, TTSCoordinator
from app.voice.tts.edge import EdgeTTSProvider
from app.voice.output_manager import VoiceOutputManager

# Vision Subsystem
from app.vision.engine import VisionEngine
from app.tools.vision_tools import (
    ScreenshotCaptureTool, ImageAnalysisTool, OCRTool,
    ScreenContextTool, ClipboardImageTool
)

class BootManager:
    """
    Orchestrates the sequential boot-up timeline of the FRIDAY Kernel, registering
    subsystem modules, dependency container singletons, and capability catalogs.
    """
    def __init__(self, container: FridayServiceContainer) -> None:
        """Initialize the BootManager."""
        self._container = container

    async def run_boot_sequence(self, config: FridayKernelConfig) -> FridayKernelContext:
        """
        Executes step-by-step DI registration, capability indexing, and context creation.
        """
        logger.info("Executing FRIDAY BootManager sequence...")
        from app.kernel.kernel import FridayKernel
        kernel = FridayKernel.get_instance()
        
        # Step 0: Startup Validation
        logger.info("Boot Step 0: Startup Validation...")
        try:
            from app.kernel.validation import validate_startup
            validation_errors = validate_startup(config)
            if validation_errors:
                for err in validation_errors:
                    logger.warning(f"Startup validation: {err}")
            else:
                logger.info("Startup validation passed - SUCCESS")
        except Exception as e:
            logger.warning(f"Startup validation skipped: {e}")
        
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
        logger.info("Event Bus registered in FridayServiceContainer.")
        
        # Step 3a: Initialize Phase 3 Intelligence Services
        logger.info("Boot Step 3a: Initialize Phase 3 Intelligence Services...")
        
        intent_analyzer = RuleBasedIntentAnalyzer(event_bus=event_bus)
        self._container.register_singleton("intent_analyzer", intent_analyzer)
        kernel.module_registry.register_module("intent_analyzer", "1.0.0", ["event_bus"], intent_analyzer)
        kernel.capability_registry.register_capability(
            name="IntentAnalysis",
            module_name="intent_analyzer",
            description="Deterministic rule-based intent classification for user queries"
        )
        
        strategy_manager = StrategyManager(event_bus=event_bus)
        self._container.register_singleton("strategy_manager", strategy_manager)
        kernel.module_registry.register_module("strategy_manager", "1.0.0", ["event_bus"], strategy_manager)
        kernel.capability_registry.register_capability(
            name="StrategyManagement",
            module_name="strategy_manager",
            description="Context-aware strategy selection and configuration management"
        )
        
        extractor_registry = ExtractorRegistry(event_bus=event_bus)
        extractor_registry.register(MemoryExtractor())
        extractor_registry.register(KnowledgeExtractor())
        extractor_registry.register(WorkflowExtractor())
        extractor_registry.register(DesktopExtractor())
        extractor_registry.register(BrowserExtractor())
        extractor_registry.register(TerminalExtractor())
        extractor_registry.register(MissionExtractor())
        extractor_registry.register(VoiceExtractor())
        extractor_registry.register(SystemStateExtractor())
        self._container.register_singleton("extractor_registry", extractor_registry)
        kernel.module_registry.register_module("extractor_registry", "1.0.0", ["event_bus"], extractor_registry)
        kernel.capability_registry.register_capability(
            name="ContextExtraction",
            module_name="extractor_registry",
            description="Multi-source context extraction from memory, knowledge, desktop, browser, terminal, missions, and workflow"
        )
        
        context_ranker = ContextRanker(event_bus=event_bus)
        self._container.register_singleton("context_ranker", context_ranker)
        kernel.module_registry.register_module("context_ranker", "1.0.0", ["event_bus"], context_ranker)
        kernel.capability_registry.register_capability(
            name="ContextRanking",
            module_name="context_ranker",
            description="Multi-dimensional relevance scoring and ranking of extracted context blocks"
        )
        
        token_allocator = AdaptiveTokenBudgetAllocator(event_bus=event_bus)
        self._container.register_singleton("token_allocator", token_allocator)
        kernel.module_registry.register_module("token_allocator", "1.0.0", ["event_bus"], token_allocator)
        kernel.capability_registry.register_capability(
            name="TokenBudgetAllocation",
            module_name="token_allocator",
            description="Adaptive token budget allocation across context blocks with provider-aware limits"
        )
        
        context_validator = ContextValidator(event_bus=event_bus)
        self._container.register_singleton("context_validator", context_validator)
        kernel.module_registry.register_module("context_validator", "1.0.0", ["event_bus"], context_validator)
        kernel.capability_registry.register_capability(
            name="ContextValidation",
            module_name="context_validator",
            description="Content quality and relevance validation of allocated context blocks"
        )
        
        context_compressor = ContextCompressor(event_bus=event_bus)
        self._container.register_singleton("context_compressor", context_compressor)
        kernel.module_registry.register_module("context_compressor", "1.0.0", ["event_bus"], context_compressor)
        kernel.capability_registry.register_capability(
            name="ContextCompression",
            module_name="context_compressor",
            description="Multi-policy context compression including light trimming, aggressive summarization, and semantic deduplication"
        )
        
        prompt_assembler = PromptAssembler(event_bus=event_bus)
        self._container.register_singleton("prompt_assembler", prompt_assembler)
        kernel.module_registry.register_module("prompt_assembler", "1.0.0", ["event_bus"], prompt_assembler)
        kernel.capability_registry.register_capability(
            name="PromptAssembly",
            module_name="prompt_assembler",
            description="Structured prompt assembly with provider-specific formatting, section ordering, and token tracking"
        )
        
        logger.info("Phase 3 Intelligence Services registered in FridayServiceContainer.")
        
        # Step 3b: Initialize Phase 5 Intelligence Pipeline Orchestrator
        logger.info("Boot Step 3b: Initialize Phase 5 Intelligence Pipeline Orchestrator...")
        
        pipeline_orchestrator = IntelligencePipeline(event_bus=event_bus)
        self._container.register_singleton("pipeline_orchestrator", pipeline_orchestrator)
        kernel.module_registry.register_module("pipeline_orchestrator", "1.0.0", ["event_bus"], pipeline_orchestrator)
        kernel.capability_registry.register_capability(
            name="IntelligencePipeline",
            module_name="pipeline_orchestrator",
            description="Deterministic 8-stage context intelligence pipeline: intent analysis through prompt assembly"
        )
        
        context_cache = ContextCache(event_bus=event_bus)
        self._container.register_singleton("context_cache", context_cache)
        kernel.module_registry.register_module("context_cache", "1.0.0", ["event_bus"], context_cache)
        kernel.capability_registry.register_capability(
            name="ContextCache",
            module_name="context_cache",
            description="Multi-level context cache with TTL, LRU eviction, pinning, and per-extractor level mapping"
        )
        
        logger.info("Phase 5 Pipeline Orchestrator and Context Cache registered in FridayServiceContainer.")
        
        # Step 4: Initialize Memory Engine
        logger.info("Boot Step 4: Initialize Memory Engine...")
        memory_engine = memory_store
        self._container.register_singleton("memory_engine", memory_engine)
        kernel.module_registry.register_module("memory_engine", "1.0.0", [], memory_engine)
        kernel.capability_registry.register_capability(
            name="Memory",
            module_name="memory_engine",
            description="Persistent and contextual Working, Session, User, and Project memory"
        )
        logger.info("Memory Engine registered in FridayServiceContainer.")
        
        # Step 5: Initialize Knowledge
        # Step 5: Initialize Knowledge Engine
        logger.info("Boot Step 5: Initialize Knowledge Engine...")
        knowledge_engine = KnowledgeEngine()
        self._container.register_singleton("knowledge_engine", knowledge_engine)
        kernel.module_registry.register_module("knowledge_engine", "1.0.0", [], knowledge_engine)
        kernel.capability_registry.register_capability(
            name="Knowledge",
            module_name="knowledge_engine",
            description="Vector DB indexing and semantic search capabilities across local workspaces"
        )
        logger.info("Knowledge Engine registered in FridayServiceContainer.")
            
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
        logger.info("Planner Engine registered in FridayServiceContainer.")
        
        # Step 7: Initialize Desktop Controller
        logger.info("Boot Step 7: Initialize Desktop Controller...")
        desktop_controller = core_desktop_controller
        self._container.register_singleton("desktop_controller", desktop_controller)
        self._container.register_singleton("tool_registry", core_tool_registry)
        kernel.module_registry.register_module("desktop_controller", "1.0.0", [], desktop_controller)
        kernel.capability_registry.register_capability(
            name="Desktop",
            module_name="desktop_controller",
            description="Direct control and automation capabilities over processes and operating system applications"
        )
        logger.info("Desktop Controller registered in FridayServiceContainer.")
        
        # Step 7b: Initialize Desktop Automation Service
        logger.info("Boot Step 7b: Initialize Desktop Automation Service...")
        desktop_automation = DesktopAutomationService()
        self._container.register_singleton("desktop_automation", desktop_automation)
        kernel.module_registry.register_module("desktop_automation", "1.0.0", [], desktop_automation)
        kernel.capability_registry.register_capability(
            name="Browser",
            module_name="desktop_automation",
            description="Headless browser navigation, text extraction, and form field filling"
        )
        logger.info("Desktop Automation Service registered in FridayServiceContainer.")
        
        # Step 7c: Initialize Tool Engine Subsystem
        logger.info("Boot Step 7c: Initialize Tool Engine...")
        tool_engine = ToolEngine()
        self._container.register_singleton("tool_engine", tool_engine)
        kernel.module_registry.register_module("tool_engine", "1.0.0", ["event_bus", "tool_registry"], tool_engine)
        logger.info("Tool Engine registered in FridayServiceContainer.")
        
        # Step 7d: Initialize Phase 6 Universal Tool Registry
        logger.info("Boot Step 7d: Initialize Phase 6 Universal Tool Registry...")
        
        universal_tool_registry = UniversalToolRegistry(event_bus=event_bus)
        self._container.register_singleton("universal_tool_registry", universal_tool_registry)
        kernel.module_registry.register_module("universal_tool_registry", "1.0.0", ["event_bus"], universal_tool_registry)

        # ── Phase 1: Activate the Universal Tool Registry ────────────────────
        # Populate it from every existing tool so discovery, selection and
        # health reporting work. The legacy registry (core_tool_registry)
        # keeps the executable BaseTool instances; the universal registry is
        # the source of truth for tool *metadata / discovery / selection*.
        from app.tools.adapter import register_tool
        from app.tools.desktop_input_tools import (
            MouseMoveTool, MouseClickTool, MouseDoubleClickTool, MouseDragDropTool,
            KeyboardTypeTool, KeyboardShortcutTool, WindowFocusTool,
            CaptureWindowTool, CaptureRegionTool,
        )
        from app.tools.vision_tools import (
            ScreenshotCaptureTool, ImageAnalysisTool, OCRTool,
            ScreenContextTool, ClipboardImageTool,
        )

        _dc = self._container.get("desktop_controller")
        _registered_ids: List[str] = []

        # 1) Tools already instantiated in the legacy registry.
        for _name, _tool in core_tool_registry.list_tools().items():
            if isinstance(_tool, BaseTool):
                register_tool(universal_tool_registry, _tool, tool_id=_name)
                _registered_ids.append(_name)

        # 2) Desktop input tools (previously never registered anywhere).
        _desktop_input = {
            MouseMoveTool: "desktop.mouse_move",
            MouseClickTool: "desktop.mouse_click",
            MouseDoubleClickTool: "desktop.mouse_double_click",
            MouseDragDropTool: "desktop.mouse_drag_drop",
            KeyboardTypeTool: "desktop.keyboard_type",
            KeyboardShortcutTool: "desktop.keyboard_shortcut",
            WindowFocusTool: "desktop.window_focus",
            CaptureWindowTool: "desktop.capture_window",
            CaptureRegionTool: "desktop.capture_region",
        }
        for _cls, _tid in _desktop_input.items():
            register_tool(universal_tool_registry, _cls(_dc), tool_id=_tid)
            _registered_ids.append(_tid)

        # 3) Vision tools (vision_engine is optional and wired later at Step 14).
        _vision = {
            ScreenshotCaptureTool: "vision.screenshot_capture",
            ImageAnalysisTool: "vision.image_analysis",
            OCRTool: "vision.ocr",
            ScreenContextTool: "vision.screen_context",
            ClipboardImageTool: "vision.clipboard_image",
        }
        for _cls, _tid in _vision.items():
            register_tool(universal_tool_registry, _cls(_dc, None), tool_id=_tid)
            _registered_ids.append(_tid)

        logger.info(
            f"Universal Tool Registry activated with {len(_registered_ids)} tools: {_registered_ids}"
        )

        kernel.capability_registry.register_capability(
            name="UniversalToolRegistry",
            module_name="universal_tool_registry",
            description="Phase 6 universal tool registry with metadata, discovery, health, dependency graph, and permissions"
        )
        logger.info("Universal Tool Registry registered in FridayServiceContainer.")
        
        # Step 7e: Initialize Tool Selection Engine
        logger.info("Boot Step 7e: Initialize Tool Selection Engine...")
        tool_selection_engine = ToolSelectionEngine(
            tool_registry=universal_tool_registry,
            event_bus=event_bus,
        )
        self._container.register_singleton("tool_selection_engine", tool_selection_engine)
        kernel.module_registry.register_module("tool_selection_engine", "1.0.0", ["event_bus", "universal_tool_registry"], tool_selection_engine)
        kernel.capability_registry.register_capability(
            name="ToolSelection",
            module_name="tool_selection_engine",
            description="Deterministic tool selection engine with 7 rule filters and 10 weighted scoring dimensions"
        )
        logger.info("Tool Selection Engine registered in FridayServiceContainer.")
        
        # Step 7f: Initialize Tool Execution Engine
        logger.info("Boot Step 7f: Initialize Tool Execution Engine...")
        legacy_tool_registry = self._container.get("tool_registry")
        tool_execution_engine = ToolExecutionEngine(
            legacy_tool_registry=legacy_tool_registry,
            universal_tool_registry=universal_tool_registry,
            event_bus=event_bus,
        )
        self._container.register_singleton("tool_execution_engine", tool_execution_engine)
        kernel.module_registry.register_module(
            "tool_execution_engine", "1.0.0",
            ["event_bus", "tool_registry", "universal_tool_registry"],
            tool_execution_engine,
        )
        kernel.capability_registry.register_capability(
            name="ToolExecution",
            module_name="tool_execution_engine",
            description="Tool execution engine with retry, timeout, cancellation, and dual-registry bridge"
        )
        logger.info("Tool Execution Engine registered in FridayServiceContainer.")
        
        # Step 7g: Initialize Workflow Engine V2
        logger.info("Boot Step 7g: Initialize Workflow Engine V2...")
        workflow_engine_v2 = WorkflowEngineV2(
            tool_execution_engine=tool_execution_engine,
            event_bus=event_bus,
        )
        self._container.register_singleton("workflow_engine_v2", workflow_engine_v2)
        kernel.module_registry.register_module(
            "workflow_engine_v2", "1.0.0",
            ["event_bus", "tool_execution_engine"],
            workflow_engine_v2,
        )
        kernel.capability_registry.register_capability(
            name="WorkflowEngineV2",
            module_name="workflow_engine_v2",
            description="Phase 6 DAG-based workflow orchestration engine reusing ToolExecutionEngine"
        )
        logger.info("Workflow Engine V2 registered in FridayServiceContainer.")
        
        # Step 7h: Initialize Mission Engine V2
        logger.info("Boot Step 7h: Initialize Mission Engine V2...")
        mission_store = MissionStore()
        checkpoint_manager = MissionCheckpointManager()
        mission_planner = MissionPlanner(mission_store)
        mission_engine_v2 = MissionExecutor(
            workflow_executor=workflow_engine_v2,
            store=mission_store,
            checkpoint_manager=checkpoint_manager,
            planner=mission_planner,
            event_bus=event_bus,
        )
        self._container.register_singleton("mission_engine_v2", mission_engine_v2)
        kernel.module_registry.register_module(
            "mission_engine_v2", "1.0.0",
            ["event_bus", "workflow_engine_v2"],
            mission_engine_v2,
        )
        kernel.capability_registry.register_capability(
            name="MissionEngineV2",
            module_name="mission_engine_v2",
            description="Phase 6 mission execution engine with pause/resume, checkpoint recovery, and background execution"
        )
        logger.info("Mission Engine V2 registered in FridayServiceContainer.")
        
        # Step 7i: Initialize Capability Registry V2
        logger.info("Boot Step 7i: Initialize Capability Registry V2...")
        capability_registry_v2 = CapabilityRegistryV2(event_bus=event_bus)
        for cap in DEFAULT_CAPABILITIES():
            capability_registry_v2.register(cap)
        self._container.register_singleton("capability_registry_v2", capability_registry_v2)
        kernel.module_registry.register_module(
            "capability_registry_v2", "1.0.0",
            ["event_bus"],
            capability_registry_v2,
        )
        kernel.capability_registry.register_capability(
            name="CapabilityRegistryV2",
            module_name="capability_registry_v2",
            description="Phase 6 capability registry with CRUD, alias resolution, search, health, permissions, and dependency graph"
        )
        logger.info("Capability Registry V2 registered in FridayServiceContainer.")
        
        # Step 7j: Initialize Capability Resolver
        logger.info("Boot Step 7j: Initialize Capability Resolver...")
        capability_resolver = CapabilityResolver(
            registry=capability_registry_v2,
            tool_selection_engine=tool_selection_engine,
            event_bus=event_bus,
        )
        self._container.register_singleton("capability_resolver", capability_resolver)
        kernel.module_registry.register_module(
            "capability_resolver", "1.0.0",
            ["event_bus", "capability_registry_v2", "tool_selection_engine"],
            capability_resolver,
        )
        kernel.capability_registry.register_capability(
            name="CapabilityResolver",
            module_name="capability_resolver",
            description="Phase 6 capability resolver with transitive dependency checking and tool selection delegation"
        )
        logger.info("Capability Resolver registered in FridayServiceContainer.")
        
        # Step 7k: Initialize Plugin SDK (Phase 7 Sprint 1)
        logger.info("Boot Step 7k: Initialize Plugin SDK...")
        plugin_permission_validator = Phase7PermissionValidator()
        plugin_permission_validator.grant("filesystem.read")
        plugin_permission_validator.grant("filesystem.write")
        plugin_permission_validator.grant("network")
        plugin_permission_validator.grant("desktop.access")
        plugin_registry = Phase7PluginRegistry(event_bus=event_bus)
        plugin_loader = Phase7PluginLoader(
            registry=plugin_registry,
            permission_validator=plugin_permission_validator,
            event_bus=event_bus,
        )
        self._container.register_singleton("plugin_registry", plugin_registry)
        self._container.register_singleton("plugin_loader", plugin_loader)
        kernel.module_registry.register_module(
            "plugin_registry", "1.0.0",
            ["event_bus"],
            plugin_registry,
        )
        kernel.module_registry.register_module(
            "plugin_loader", "1.0.0",
            ["event_bus", "plugin_registry"],
            plugin_loader,
        )
        kernel.capability_registry.register_capability(
            name="PluginSDK",
            module_name="plugin_registry",
            description="Plugin SDK for local FRIDAY extensions with manifest validation, dependency resolution, permission model, and lifecycle management"
        )
        logger.info("Plugin SDK registered in FridayServiceContainer.")
        
        # Step 7l: Initialize Plugin Runtime (Phase 7 Sprint 2)
        logger.info("Boot Step 7l: Initialize Plugin Runtime...")
        plugin_runtime_config = PluginRuntimeConfig()
        plugin_runtime = PluginRuntime(
            sdk_registry=plugin_registry,
            event_bus=event_bus,
            config=plugin_runtime_config,
        )
        self._container.register_singleton("plugin_runtime", plugin_runtime)
        kernel.module_registry.register_module(
            "plugin_runtime", "1.0.0",
            ["event_bus", "plugin_registry", "plugin_loader"],
            plugin_runtime,
        )
        kernel.capability_registry.register_capability(
            name="PluginRuntime",
            module_name="plugin_runtime",
            description="Phase 7 Plugin Runtime with sandboxed execution, hot reload, lifecycle management, and resource monitoring"
        )
        logger.info("Plugin Runtime registered in FridayServiceContainer.")
        
        # Step 7m: Initialize Plugin Marketplace (Phase 7 Sprint 3)
        logger.info("Boot Step 7m: Initialize Plugin Marketplace...")
        marketplace_config = MarketplaceConfig(
            local_repository_path="./plugins",
        )
        package_manager = PackageManager(
            runtime=plugin_runtime,
            event_bus=event_bus,
            config=marketplace_config,
        )
        self._container.register_singleton("package_manager", package_manager)
        kernel.module_registry.register_module(
            "package_manager", "1.0.0",
            ["event_bus", "plugin_registry", "plugin_runtime"],
            package_manager,
        )
        kernel.capability_registry.register_capability(
            name="PluginMarketplace",
            module_name="package_manager",
            description="Phase 7 Plugin Marketplace and Package Manager with dependency resolution, updates, rollback, and cache"
        )
        logger.info("Plugin Marketplace registered in FridayServiceContainer.")
        
        # Step 7n: Initialize Plugin Security (Phase 7 Sprint 4)
        logger.info("Boot Step 7n: Initialize Plugin Security...")
        plugin_signer = PluginSigner(secret_key="")
        trust_store = TrustStore()
        publisher_registry = PublisherRegistry()
        repo_policy_manager = RepositoryPolicyManager()
        integrity_verifier = IntegrityVerifier()
        plugin_verifier = PluginVerifier(
            signer=plugin_signer,
            trust_store=trust_store,
            policy_manager=repo_policy_manager,
            integrity=integrity_verifier,
        )
        update_policy = UpdatePolicy()
        self._container.register_singleton("plugin_security", plugin_verifier)
        self._container.register_singleton("trust_store", trust_store)
        self._container.register_singleton("publisher_registry", publisher_registry)
        self._container.register_singleton("repository_policy", repo_policy_manager)

        kernel.module_registry.register_module(
            "plugin_security", "1.0.0",
            ["event_bus", "plugin_registry", "plugin_runtime", "package_manager"],
            plugin_verifier,
        )
        kernel.module_registry.register_module(
            "plugin_signer", "1.0.0", [], plugin_signer,
        )
        kernel.module_registry.register_module(
            "trust_store", "1.0.0", [], trust_store,
        )
        kernel.module_registry.register_module(
            "publisher_registry", "1.0.0", [], publisher_registry,
        )
        kernel.module_registry.register_module(
            "repository_policy", "1.0.0", [], repo_policy_manager,
        )
        kernel.capability_registry.register_capability(
            name="PluginSecurity",
            module_name="plugin_security",
            description="Phase 7 Plugin Security with cryptographic verification, trusted publishers, repository trust policies, secure updates, and rollback protection"
        )
        logger.info("Plugin Security registered in FridayServiceContainer.")
        
        # Step 7o: Initialize Multi-Agent Framework (Phase 8 Sprint 1)
        logger.info("Boot Step 7o: Initialize Multi-Agent Framework...")
        agent_manager = AgentManager()
        if event_bus is not None:
            agent_manager.set_event_bus(event_bus)
        builtin_agents = create_all_builtin_agents()
        for agent in builtin_agents:
            agent_manager.create_agent(
                agent_id=agent.agent_id,
                name=agent.name,
                role=agent.role,
                capabilities=agent.capabilities,
                tools=agent.tools,
                permissions=agent.permissions,
                priority=agent.priority,
                memory_scope=agent.memory_scope,
            )
        self._container.register_singleton("agent_manager", agent_manager)
        kernel.module_registry.register_module(
            "agent_manager", "1.0.0",
            ["event_bus", "plugin_registry", "plugin_runtime", "memory_engine", "knowledge_engine", "planner"],
            agent_manager,
        )
        kernel.capability_registry.register_capability(
            name="MultiAgentFramework",
            module_name="agent_manager",
            description="Phase 8 multi-agent orchestration framework with 7 built-in specialized agents, inter-agent communication, scheduling, permissions, and health monitoring"
        )
        logger.info("Multi-Agent Framework registered in FridayServiceContainer.")
        
        # Step 7p: Initialize Agent Framework Enhancements (Phase 8 Sprint 2)
        logger.info("Boot Step 7p: Initialize Agent Framework Enhancements...")
        try:
            key_lock_manager = KeyLockManager()
            kernel.module_registry.register_module(
                "key_lock_manager", "1.0.0", [], key_lock_manager,
            )
            
            blackboard = Blackboard(lock_manager=key_lock_manager)
            self._container.register_singleton("blackboard", blackboard)
            kernel.module_registry.register_module(
                "blackboard", "1.0.0", ["key_lock_manager"], blackboard,
            )
            kernel.capability_registry.register_capability(
                name="SharedBlackboard",
                module_name="blackboard",
                description="Phase 8 shared blackboard for inter-agent collaboration with versioning, conflict detection, and locking",
            )
            
            delegation_manager = DelegationManager()
            self._container.register_singleton("delegation_manager", delegation_manager)
            kernel.module_registry.register_module(
                "delegation_manager", "1.0.0", [], delegation_manager,
            )
            kernel.capability_registry.register_capability(
                name="AgentDelegation",
                module_name="delegation_manager",
                description="Phase 8 task delegation with sub-task creation, dependency tracking, parent-child relationships, and completion propagation",
            )
            
            priority_engine = PriorityEngine()
            kernel.module_registry.register_module(
                "priority_engine", "1.0.0", [], priority_engine,
            )
            
            coordinator = Coordinator(
                agent_manager=agent_manager,
                delegation_manager=delegation_manager,
                blackboard=blackboard,
                priority_engine=priority_engine,
                metrics=agent_manager.metrics,
            )
            self._container.register_singleton("coordinator", coordinator)
            kernel.module_registry.register_module(
                "coordinator", "1.0.0",
                ["agent_manager", "delegation_manager", "blackboard", "priority_engine"],
                coordinator,
            )
            kernel.capability_registry.register_capability(
                name="AgentCoordinator",
                module_name="coordinator",
                description="Phase 8 agent coordinator with parallel/serial/dependency-aware execution, priority queues, and resource allocation",
            )
            
            consensus_engine = ConsensusEngine()
            kernel.module_registry.register_module(
                "consensus_engine", "1.0.0", [], consensus_engine,
            )
            kernel.capability_registry.register_capability(
                name="AgentConsensus",
                module_name="consensus_engine",
                description="Phase 8 deterministic decision strategies: majority vote, priority override, coordinator decision, unanimous approval",
            )
            
            persistence_manager = PersistenceManager()
            self._container.register_singleton("persistence_manager", persistence_manager)
            kernel.module_registry.register_module(
                "persistence_manager", "1.0.0", [], persistence_manager,
            )
            kernel.capability_registry.register_capability(
                name="AgentPersistence",
                module_name="persistence_manager",
                description="Phase 8 agent state persistence with checkpoint/restore, warm restart, and crash recovery support",
            )
            
            recovery_manager = RecoveryManager(
                persistence=persistence_manager,
                agent_manager=agent_manager,
                delegation=delegation_manager,
                blackboard=blackboard,
                metrics=agent_manager.metrics,
            )
            self._container.register_singleton("recovery_manager", recovery_manager)
            kernel.module_registry.register_module(
                "recovery_manager", "1.0.0",
                ["persistence_manager", "agent_manager", "delegation_manager", "blackboard"],
                recovery_manager,
            )
            kernel.capability_registry.register_capability(
                name="AgentRecovery",
                module_name="recovery_manager",
                description="Phase 8 automatic recovery after restart with agent state, delegated work, and shared context restoration",
            )
            
            metrics_collector = MetricsCollector()
            self._container.register_singleton("metrics_collector", metrics_collector)
            kernel.module_registry.register_module(
                "metrics_collector", "1.0.0", [], metrics_collector,
            )
            kernel.capability_registry.register_capability(
                name="AgentMetrics",
                module_name="metrics_collector",
                description="Phase 8 agent metrics tracking: delegation count, parallel efficiency, queue latency, agent utilization, recovery statistics",
            )
            
            logger.info("Agent Framework Enhancements registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Agent Framework Enhancements: {str(e)}")
            raise e
        
        # Step 7q: Initialize Cognitive Planning Engine (Phase 8 Sprint 3)
        logger.info("Boot Step 7q: Initialize Cognitive Planning Engine...")
        try:
            planning_engine = PlanningEngine(agent_manager=agent_manager)
            if event_bus is not None:
                planning_engine.set_event_bus(event_bus)
            self._container.register_singleton("planning_engine", planning_engine)
            kernel.module_registry.register_module(
                "planning_engine", "1.0.0",
                ["event_bus", "agent_manager"],
                planning_engine,
            )
            kernel.capability_registry.register_capability(
                name="CognitivePlanning",
                module_name="planning_engine",
                description="Phase 8 symbolic cognitive planning engine with goal decomposition, DAG planning, constraint validation, simulation, heuristics, plan memory, and optimization",
            )
            logger.info("Cognitive Planning Engine registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Cognitive Planning Engine: {str(e)}")
            raise e

        # Step 7qr: Initialize Cognitive Core (Milestone 2 — Planner + Graph + Orchestration)
        logger.info("Boot Step 7qr: Initialize Cognitive Core...")
        try:
            cognitive_core = CognitiveCore(
                event_bus=event_bus,
                planning_engine=planning_engine,
                universal_tool_registry=universal_tool_registry,
            )
            self._container.register_singleton("cognitive_core", cognitive_core)
            kernel.module_registry.register_module(
                "cognitive_core", "1.0.0",
                ["event_bus", "planning_engine", "universal_tool_registry"],
                cognitive_core,
            )
            kernel.capability_registry.register_capability(
                name="CognitiveCore",
                module_name="cognitive_core",
                description="Unified facade: UnifiedPlanner + CognitiveGraph + SemanticMemory orchestration with failure recovery and hybrid retrieval",
            )
            logger.info("Cognitive Core registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Cognitive Core: {str(e)}")
            raise e

        # Step 7rs: Initialize Unified Execution Engine (Milestone 4)
        logger.info("Boot Step 7rs: Initialize Unified Execution Engine...")
        try:
            from app.execution.integration import create_execution_engine
            execution_engine = create_execution_engine(
                kernel,
                config=None,
            )
            self._container.register_singleton("execution_engine", execution_engine)
            kernel.module_registry.register_module(
                "execution_engine", "1.0.0",
                ["event_bus", "llm_router", "memory_engine", "planner",
                 "tool_registry", "runtime_scheduler_bridge", "mission_runtime",
                 "cognitive_core", "tool_selection_engine", "tool_execution_engine",
                 "plugin_runtime"],
                execution_engine,
            )
            kernel.capability_registry.register_capability(
                name="UnifiedExecutionEngine",
                module_name="execution_engine",
                description="Milestone 4 unified execution pipeline with cancellation, retry, timeout, middleware, progress events, and per-stage metrics",
            )
            logger.info("Unified Execution Engine registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Unified Execution Engine: {str(e)}")
            raise e

        # Step 7s: Initialize Autonomous Development System (Milestone 7)
        logger.info("Boot Step 7s: Initialize Autonomous Development System...")
        try:
            from app.autonomous_dev.planner import AutonomousPlanner
            from app.autonomous_dev.executor import AutonomousExecutor
            from app.autonomous_dev.reflection import AutonomousReflection
            from app.autonomous_dev.manager import AutonomousDevelopmentManager
            from app.core.dependencies import workspace_manager, document_indexer

            # The reflection engine needs the learning engine from memory
            memory_engine_service = self._container.get("memory_engine")
            learning_engine = getattr(memory_engine_service, "_learning", None)

            autonomous_planner = AutonomousPlanner(memory_engine=memory_engine_service)
            self._container.register_singleton("autonomous_planner", autonomous_planner)
            kernel.module_registry.register_module("autonomous_planner", "1.0.0", ["memory_engine"], autonomous_planner)

            autonomous_executor = AutonomousExecutor(
                workspace_manager=workspace_manager,
                document_indexer=document_indexer
            )
            self._container.register_singleton("autonomous_executor", autonomous_executor)
            kernel.module_registry.register_module("autonomous_executor", "1.0.0", [], autonomous_executor)

            autonomous_reflection = AutonomousReflection(
                learning_engine=learning_engine,
                event_bus=event_bus
            )
            self._container.register_singleton("reflection_engine_v2", autonomous_reflection) # Note: reusing v2 name for now
            kernel.module_registry.register_module("autonomous_reflection", "1.0.0", ["memory_engine", "event_bus"], autonomous_reflection)

            autonomous_manager = AutonomousDevelopmentManager(event_bus=event_bus)
            self._container.register_singleton("autonomous_manager", autonomous_manager)
            kernel.module_registry.register_module("autonomous_manager", "1.0.0", ["event_bus", "autonomous_planner", "autonomous_executor", "autonomous_reflection"], autonomous_manager)

            kernel.capability_registry.register_capability(
                name="AutonomousDevelopment",
                module_name="autonomous_manager",
                description="Milestone 7 Autonomous Development System for self-improvement and project analysis.",
            )
            logger.info("Autonomous Development System registered in FridayServiceContainer.")

            # Initialize FACS System integration (AI Continuity)
            logger.info("Boot Step 7f: Initialize FACS Subsystem...")
            from app.facs.subscriber import FACSSubscriber
            facs_subscriber = FACSSubscriber(event_bus=event_bus)
            await facs_subscriber.initialize()
            self._container.register_singleton("facs_subscriber", facs_subscriber)
            logger.info("FACS Subsystem event listener registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Autonomous Development System: {str(e)}", exc_info=True)
            raise e

        # Step 7r: Initialize Autonomous Mission Runtime (Phase 9 Sprint 1)
        logger.info("Boot Step 7r: Initialize Autonomous Mission Runtime...")
        try:
            runtime = MissionRuntime(
                agent_manager=agent_manager,
                planning_engine=planning_engine,
                memory_engine=memory_engine,
                plan_memory=planning_engine._memory if hasattr(planning_engine, '_memory') else None,
            )
            if event_bus is not None:
                runtime.set_event_bus(event_bus)
            self._container.register_singleton("mission_runtime", runtime)
            kernel.module_registry.register_module(
                "mission_runtime", "1.0.0",
                ["event_bus", "agent_manager", "planning_engine"],
                runtime,
            )
            kernel.capability_registry.register_capability(
                name="AutonomousMissionRuntime",
                module_name="mission_runtime",
                description="Phase 9 autonomous mission runtime connecting intent analysis, planning, capability resolution, tool selection, workflow generation, agent assignment, execution, monitoring, recovery, reflection, and memory update into one automated lifecycle",
            )
            logger.info("Autonomous Mission Runtime registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Autonomous Mission Runtime: {str(e)}")
            raise e

        # Step 7s: Initialize MCP Runtime (Phase 6)
        logger.info("Boot Step 7s: Initialize MCP Runtime...")
        try:
            from app.mcp_runtime.base import MCPConnectionConfig, MCPTransportType
            from app.mcp_runtime.integration import create_mcp_runtime

            universal_tool_registry = self._container.get("universal_tool_registry")
            legacy_tool_registry = self._container.get("tool_registry")

            mcp_server_configs = [
                MCPConnectionConfig(
                    server_name=s.server_name,
                    transport=MCPTransportType(s.transport),
                    command=s.command,
                    args=list(s.args),
                    url=s.url,
                    api_key=s.api_key,
                    timeout_seconds=s.timeout_seconds,
                    auto_reconnect=s.auto_reconnect,
                )
                for s in config.mcp.servers
            ]

            mcp_registry = await create_mcp_runtime(
                event_bus=event_bus,
                universal_registry=universal_tool_registry,
                legacy_registry=legacy_tool_registry,
                server_configs=mcp_server_configs,
            )
            self._container.register_singleton("mcp_registry", mcp_registry)
            kernel.module_registry.register_module(
                "mcp_registry", "1.0.0",
                ["event_bus", "universal_tool_registry", "tool_registry"],
                mcp_registry,
            )
            kernel.capability_registry.register_capability(
                name="MCPRuntime",
                module_name="mcp_registry",
                description="Phase 6 Universal MCP Runtime — multi-server MCP client registry, tool discovery, and tool call execution",
            )
            logger.info(
                f"MCP Runtime registered in FridayServiceContainer with "
                f"{len(mcp_server_configs)} configured servers"
            )
        except Exception as e:
            logger.error(f"Failed to initialize MCP Runtime: {str(e)}")
            raise e

        # Step 8: Initialize Mission Engine
        logger.info("Boot Step 8: Initialize Mission Engine...")
        telemetry = MissionTelemetry()
        self._container.register_singleton("telemetry", telemetry)
        kernel.module_registry.register_module("telemetry", "1.0.0", [], telemetry)
        history = MissionHistory()
        kernel.module_registry.register_module("history", "1.0.0", [], history)
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
        logger.info("Mission Engine (MissionManager) registered in FridayServiceContainer.")
        
        # Step 9: Initialize Workflow Engine (full DI)
        logger.info("Boot Step 9: Initialize Workflow Engine...")
        workflow_history = WorkflowHistory()
        kernel.module_registry.register_module("workflow_history", "1.0.0", [], workflow_history)
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
        logger.info("Workflow Engine (full) registered in FridayServiceContainer.")
        
        # Step 10: Initialize Scheduler
        logger.info("Boot Step 10: Initialize Scheduler...")
        scheduler = FridayScheduler()
        self._container.register_singleton("scheduler", scheduler)
        kernel.module_registry.register_module("scheduler", "1.0.0", [], scheduler)
        kernel.capability_registry.register_capability(
            name="Calendar",
            module_name="scheduler",
            description="Time-based event triggers, cron actions scheduling, and notification alarms"
        )
        logger.info("Scheduler registered in FridayServiceContainer.")
        
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
        logger.info("LLM Router registered in FridayServiceContainer.")
        
        # Late-bind LLM Router into Workflow Engine
        workflow_engine._llm_router = llm_router
        logger.info("LLM Router late-bound into Workflow Engine.")
        
        # Step 11: Initialize Multi-Agent Runtime (Alpha 4.5)
        logger.info("Boot Step 11: Initialize Multi-Agent Runtime...")
        try:
            agent_message_bus = AgentMessageBus(event_bus=event_bus)
            self._container.register_singleton("agent_message_bus", agent_message_bus)
            kernel.module_registry.register_module("agent_message_bus", "1.0.0", ["event_bus"], agent_message_bus)

            agent_registry = AgentRegistry(
                event_bus=event_bus,
                message_bus=agent_message_bus
            )
            self._container.register_singleton("agent_registry", agent_registry)
            kernel.module_registry.register_module("agent_registry", "1.0.0", ["event_bus", "agent_message_bus"], agent_registry)

            agent_scheduler = AgentScheduler(event_bus=event_bus)
            self._container.register_singleton("agent_scheduler", agent_scheduler)
            kernel.module_registry.register_module("agent_scheduler", "1.0.0", ["event_bus"], agent_scheduler)

            agent_telemetry = AgentTelemetry(event_bus=event_bus)
            self._container.register_singleton("agent_telemetry", agent_telemetry)
            kernel.module_registry.register_module("agent_telemetry", "1.0.0", ["event_bus"], agent_telemetry)

            shared_context = SharedContext(kernel=kernel, event_bus=event_bus)
            self._container.register_singleton("shared_context", shared_context)
            kernel.module_registry.register_module("shared_context", "1.0.0", ["event_bus"], shared_context)

            agent_coordinator = AgentCoordinator(
                registry=agent_registry,
                message_bus=agent_message_bus,
                scheduler=agent_scheduler,
                telemetry=agent_telemetry,
                shared_context=shared_context,
                event_bus=event_bus
            )
            self._container.register_singleton("agent_coordinator", agent_coordinator)

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
            logger.info("Multi-Agent Runtime registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Multi-Agent Runtime: {str(e)}")
            raise e

        # Step 12: Initialize Workflow Runtime (Alpha 5.0)
        logger.info("Boot Step 12: Initialize Workflow Runtime...")
        try:
            persist_dir = getattr(config.paths, "persist_dir", getattr(config.paths, "workspace_root", "./data"))
            workflow_persistence = WorkflowPersistence(persist_dir=persist_dir)
            kernel.module_registry.register_module("workflow_persistence", "1.0.0", [], workflow_persistence)

            checkpoint_manager = WorkflowCheckpointManager(persist_dir=persist_dir)
            kernel.module_registry.register_module("checkpoint_manager", "1.0.0", [], checkpoint_manager)

            workflow_worker = WorkflowWorkerAgent(
                agent_id="workflow-worker",
                name="Workflow Worker",
                shared_context=shared_context
            )
            await agent_registry.register(workflow_worker)
            workflow_worker.set_context(shared_context)
            kernel.module_registry.register_module("workflow_worker_agent", "1.0.0", ["shared_context"], workflow_worker)

            runtime_executor = WorkflowRuntimeExecutor(
                agent_coordinator=agent_coordinator,
                shared_context=shared_context,
                checkpoint_manager=checkpoint_manager,
                event_bus=event_bus,
            )
            kernel.module_registry.register_module("workflow_runtime_executor", "1.0.0", ["agent_coordinator", "shared_context", "checkpoint_manager"], runtime_executor)

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
            kernel.module_registry.register_module("runtime_scheduler_bridge", "1.0.0", ["workflow_runtime", "agent_scheduler"], scheduler_bridge)

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
            logger.info("Workflow Runtime registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Workflow Runtime: {str(e)}")
            raise e

        # Step 13: Initialize Voice Subsystem
        logger.info("Boot Step 13: Initialize Voice Subsystem...")
        try:
            from app.api.routes import get_orchestrator
            
            # Resolve Gemini Adapter from llm_router for STT provider
            llm_router = self._container.get("llm_router")
            gemini_adapter = llm_router.get_provider("gemini") if llm_router else None
            
            speech_provider = GeminiSpeechProvider(gemini_adapter) if gemini_adapter else None
            
            # Register new Voice Output components
            voice_state_machine = VoiceStateMachine()
            self._container.register_singleton("voice_state_machine", voice_state_machine)
            kernel.module_registry.register_module("voice_state_machine", "1.0.0", [], voice_state_machine)

            tts_registry = TTSProviderRegistry()
            mock_tts = MockTTSProvider()
            edge_tts_prov = EdgeTTSProvider()
            tts_registry.register(mock_tts, is_default=False)
            tts_registry.register(edge_tts_prov, is_default=True)
            self._container.register_singleton("tts_provider_registry", tts_registry)
            kernel.module_registry.register_module("tts_provider_registry", "1.0.0", [], tts_registry)

            tts_coordinator = TTSCoordinator(tts_registry)
            self._container.register_singleton("tts_coordinator", tts_coordinator)
            kernel.module_registry.register_module("tts_coordinator", "1.0.0", ["tts_provider_registry"], tts_coordinator)

            voice_output_manager = VoiceOutputManager(tts_coordinator)
            self._container.register_singleton("voice_output_manager", voice_output_manager)
            kernel.module_registry.register_module("voice_output_manager", "1.0.0", ["tts_coordinator"], voice_output_manager)
            
            voice_manager = VoiceSessionManager(
                event_bus=event_bus,
                orchestrator_factory=get_orchestrator,
                speech_provider=speech_provider,
                state_machine=voice_state_machine,
                tts_coordinator=tts_coordinator,
                voice_output_manager=voice_output_manager
            )
            self._container.register_singleton("voice_manager", voice_manager)
            kernel.module_registry.register_module(
                "voice_manager", "1.0.0", 
                ["event_bus", "llm_router", "voice_state_machine", "tts_coordinator", "voice_output_manager"], 
                voice_manager
            )
            
            logger.info("Voice Subsystem registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Voice Subsystem: {str(e)}")
            raise e

        # Step 14: Initialize Vision Subsystem
        logger.info("Boot Step 14: Initialize Vision Subsystem...")
        try:
            desktop_controller = self._container.get("desktop_controller")
            vision_engine = VisionEngine(
                event_bus=event_bus,
                desktop_controller=desktop_controller,
            )
            await vision_engine.initialize()
            self._container.register_singleton("vision_engine", vision_engine)
            kernel.module_registry.register_module(
                "vision_engine", "1.0.0",
                ["event_bus", "desktop_controller"],
                vision_engine
            )

            tool_registry = self._container.get("tool_registry")
            if tool_registry:
                tool_registry.register("vision.screenshot", ScreenshotCaptureTool(desktop_controller, vision_engine))
                tool_registry.register("vision.analyze", ImageAnalysisTool(desktop_controller, vision_engine))
                tool_registry.register("vision.ocr", OCRTool(desktop_controller, vision_engine))
                tool_registry.register("vision.screen_context", ScreenContextTool(desktop_controller, vision_engine))
                tool_registry.register("vision.clipboard_image", ClipboardImageTool(desktop_controller, vision_engine))
                logger.info("Vision tools registered in ToolRegistry.")
            logger.info("Vision Subsystem registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Vision Subsystem: {str(e)}")
            raise e

        # Step 14b: Initialize Desktop Intelligence Service (Milestone 5)
        logger.info("Boot Step 14b: Initialize Desktop Intelligence Service...")
        try:
            desktop_controller = self._container.get("desktop_controller")
            vision_engine = self._container.get("vision_engine")
            desktop_intelligence = DesktopIntelligence(
                desktop_controller=desktop_controller,
                vision_engine=vision_engine,
                event_bus=event_bus,
            )
            self._container.register_singleton("desktop_intelligence", desktop_intelligence)
            kernel.module_registry.register_module(
                "desktop_intelligence", "1.0.0",
                ["event_bus", "desktop_controller", "vision_engine"],
                desktop_intelligence,
            )
            kernel.capability_registry.register_capability(
                name="DesktopIntelligence",
                module_name="desktop_intelligence",
                description="Milestone 5 unified desktop state aggregation — windows, clipboard, processes, screen context, OCR — for intelligent planning and execution",
            )

            # Register DesktopIntelligenceExtractor in the extraction pipeline
            extractor_registry = self._container.get("extractor_registry")
            di_extractor = DesktopIntelligenceExtractor(desktop_intelligence=desktop_intelligence)
            extractor_registry.register(di_extractor)
            logger.info("DesktopIntelligenceExtractor registered in extractor registry.")

            # Wire DesktopContextMiddleware into the execution engine
            execution_engine = self._container.get("execution_engine")
            di_middleware = DesktopContextMiddleware(desktop_intelligence=desktop_intelligence)
            execution_engine.add_middleware(di_middleware)
            logger.info("DesktopContextMiddleware wired into execution engine.")

            logger.info("Desktop Intelligence Service registered in FridayServiceContainer.")
        except Exception as e:
            logger.error(f"Failed to initialize Desktop Intelligence Service: {str(e)}")
            raise e

        # Construct Context
        user_ctx = UserContext()
        mission_ctx = MissionContext()
        workspace_ctx = WorkspaceContext(active_workspace_path=config.paths.workspace_root)
        metadata = SystemMetadata()
        
        context = FridayKernelContext(
            user=user_ctx,
            mission=mission_ctx,
            workspace=workspace_ctx,
            loaded_services=self._container.list_services(),
            state=KernelState.READY,
            config=config,
            metadata=metadata
        )
        
        logger.info("Boot Step 15: Ready - Boot sequence completed successfully.")
        return context
