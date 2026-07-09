from typing import Optional, Any, Dict
from loguru import logger


class PluginContext:
    def __init__(
        self,
        plugin_id: str,
        plugin_name: str,
        event_bus: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        planner: Optional[Any] = None,
        cognitive_core: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self._event_bus = event_bus
        self._tool_registry = tool_registry
        self._memory = memory_manager
        self._planner = planner
        self._cognitive_core = cognitive_core
        self._config = config or {}
        self._settings: Dict[str, Any] = {}

    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, self._config.get(key, default))

    def update_setting(self, key: str, value: Any) -> None:
        self._settings[key] = value

    def log_debug(self, msg: str) -> None:
        logger.debug(f"[Plugin:{self.plugin_name}] {msg}")

    def log_info(self, msg: str) -> None:
        logger.info(f"[Plugin:{self.plugin_name}] {msg}")

    def log_warning(self, msg: str) -> None:
        logger.warning(f"[Plugin:{self.plugin_name}] {msg}")

    def log_error(self, msg: str) -> None:
        logger.error(f"[Plugin:{self.plugin_name}] {msg}")

    def publish_event(self, topic: str, data: Dict[str, Any]) -> None:
        if not self._event_bus:
            return
        try:
            from app.events.events import FridayEvent
            event = FridayEvent(topic=topic, data=data)
            self._event_bus.publish_background(event)
        except Exception as e:
            self.log_error(f"Failed to publish event '{topic}': {e}")

    def register_tool(self, tool_id: str, tool_instance: Any) -> bool:
        if not self._tool_registry:
            self.log_error("No tool registry available")
            return False
        try:
            if hasattr(self._tool_registry, "register"):
                self._tool_registry.register(tool_id, tool_instance)
                self.log_info(f"Registered tool '{tool_id}'")
                return True
            if hasattr(self._tool_registry, "list_tools"):
                registry_map = self._tool_registry.list_tools()
                if isinstance(registry_map, dict):
                    registry_map[tool_id] = tool_instance
                    self.log_info(f"Registered tool '{tool_id}'")
                    return True
        except Exception as e:
            self.log_error(f"Failed to register tool '{tool_id}': {e}")
        return False

    def unregister_tool(self, tool_id: str) -> bool:
        if not self._tool_registry:
            return False
        try:
            if hasattr(self._tool_registry, "unregister"):
                self._tool_registry.unregister(tool_id)
                return True
            reg = self._tool_registry.list_tools()
            if isinstance(reg, dict) and tool_id in reg:
                del reg[tool_id]
                return True
        except Exception:
            pass
        return False

    async def query_memory(self, query: str, limit: int = 5) -> list:
        if not self._memory:
            return []
        try:
            if hasattr(self._memory, "retrieve_relevant_context"):
                return self._memory.retrieve_relevant_context(query, limit=limit)
            if hasattr(self._memory, "search"):
                return await self._memory.search(query, top_k=limit)
        except Exception as e:
            self.log_error(f"Memory query failed: {e}")
        return []

    async def create_plan(self, prompt: str) -> Any:
        if not self._planner:
            return None
        try:
            if hasattr(self._planner, "plan"):
                return await self._planner.plan(prompt)
        except Exception as e:
            self.log_error(f"Planner call failed: {e}")
        return None

    async def retrieve_context(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        if not self._cognitive_core:
            return {}
        try:
            if hasattr(self._cognitive_core, "retrieve_relevant_context"):
                return await self._cognitive_core.retrieve_relevant_context(query, top_k=top_k)
        except Exception as e:
            self.log_error(f"Cognitive retrieval failed: {e}")
        return {}
