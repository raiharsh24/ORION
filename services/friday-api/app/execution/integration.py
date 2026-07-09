from typing import Optional, Any
from loguru import logger

from app.execution.engine import UnifiedExecutionEngine
from app.execution.config import ExecutionConfig
from app.execution.middleware_hooks import PluginHookMiddleware


def create_execution_engine(kernel: Any, config: Optional[ExecutionConfig] = None) -> UnifiedExecutionEngine:
    event_bus = kernel.get_service("event_bus")
    memory = kernel.get_service("memory_engine")
    llm_router = kernel.get_service("llm_router")
    planner = kernel.get_service("planner")
    tool_registry = kernel.get_service("tool_registry")
    runtime_bridge = kernel.get_service("runtime_scheduler_bridge")
    mission_runtime = kernel.get_service("mission_runtime")
    cognitive_core = kernel.get_service("cognitive_core")
    tool_selection_engine = kernel.get_service("tool_selection_engine")
    tool_execution_engine = kernel.get_service("tool_execution_engine")
    plugin_runtime = kernel.get_service("plugin_runtime")

    from app.friday.intent import IntentClassifier
    from app.friday.prompt_manager import PromptManager
    from app.memory import EmbeddingsManager

    engine = UnifiedExecutionEngine(
        llm_router=llm_router,
        intent_classifier=IntentClassifier(),
        memory=memory,
        prompt_manager=PromptManager(),
        tool_registry=tool_registry,
        embeddings=EmbeddingsManager(),
        runtime_bridge=runtime_bridge,
        event_bus=event_bus,
        mission_runtime=mission_runtime,
        cognitive_core=cognitive_core,
        tool_selection_engine=tool_selection_engine,
        tool_execution_engine=tool_execution_engine,
        plugin_runtime=plugin_runtime,
        config=config,
    )

    engine.add_middleware(PluginHookMiddleware(plugin_runtime=plugin_runtime))

    logger.info("UnifiedExecutionEngine created and wired into kernel services")
    return engine
