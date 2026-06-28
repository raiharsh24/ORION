from typing import Dict, Any, List, Optional
from loguru import logger


class SharedContext:
    def __init__(self, kernel: Any, event_bus: Any) -> None:
        self._kernel = kernel
        self._event_bus = event_bus

    @property
    def kernel(self) -> Any:
        return self._kernel

    @property
    def memory(self) -> Any:
        return self._kernel.get_service("memory_engine")

    @property
    def planner(self) -> Any:
        return self._kernel.get_service("planner")

    @property
    def knowledge(self) -> Any:
        return self._kernel.get_service("knowledge_engine")

    @property
    def tools(self) -> Any:
        return self._kernel.get_service("tool_engine")

    @property
    def tool_registry(self) -> Any:
        return self._kernel.get_service("tool_registry")

    @property
    def llm(self) -> Any:
        return self._kernel.get_service("llm_router")

    @property
    def desktop(self) -> Any:
        return self._kernel.get_service("desktop_controller")

    @property
    def automation(self) -> Any:
        return self._kernel.get_service("desktop_automation")

    @property
    def workflow(self) -> Any:
        return self._kernel.get_service("workflow_engine")

    @property
    def scheduler(self) -> Any:
        return self._kernel.get_service("scheduler")

    @property
    def event_bus(self) -> Any:
        return self._event_bus

    async def store_memory(
        self,
        agent_id: str,
        key: str,
        value: Any,
        layer: str = "working"
    ) -> None:
        memory = self.memory
        if memory and hasattr(memory, "store"):
            try:
                await memory.store(layer=layer, key=key, value=value, agent_id=agent_id)
            except Exception as e:
                logger.error(f"SharedContext memory store failed: {e}")

    async def retrieve_memory(self, key: str, layer: str = "working") -> Optional[Any]:
        memory = self.memory
        if memory and hasattr(memory, "retrieve"):
            try:
                return await memory.retrieve(layer=layer, key=key)
            except Exception as e:
                logger.error(f"SharedContext memory retrieve failed: {e}")
        return None

    async def query_knowledge(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        knowledge = self.knowledge
        if knowledge and hasattr(knowledge, "retrieve"):
            try:
                return await knowledge.retrieve(query, top_k=top_k)
            except Exception as e:
                logger.error(f"SharedContext knowledge query failed: {e}")
        return []

    async def plan_task(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Any:
        planner = self.planner
        if planner and hasattr(planner, "plan"):
            try:
                return await planner.plan(goal=goal, context=context or {})
            except Exception as e:
                logger.error(f"SharedContext plan failed: {e}")
        return None

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        tools = self.tools
        if tools and hasattr(tools, "execute"):
            try:
                return await tools.execute(tool_name=tool_name, args=kwargs)
            except Exception as e:
                logger.error(f"SharedContext tool execution failed: {e}")
        return None

    async def generate_llm(self, prompt: str, provider: Optional[str] = None) -> str:
        llm = self.llm
        if llm and hasattr(llm, "generate"):
            try:
                return await llm.generate(prompt=prompt, provider=provider)
            except Exception as e:
                logger.error(f"SharedContext LLM generation failed: {e}")
        return ""

    async def publish_event(self, topic: str, data: Dict[str, Any]) -> None:
        if self._event_bus:
            from app.events.events import OrionEvent
            try:
                await self._event_bus.publish(OrionEvent(topic, data))
            except Exception as e:
                logger.error(f"SharedContext event publish failed: {e}")

    def health(self) -> Dict[str, Any]:
        available = []
        unavailable = []
        for svc in ["memory_engine", "planner", "knowledge_engine", "tool_engine",
                     "llm_router", "workflow_engine", "tool_registry"]:
            if self._kernel.get_service(svc):
                available.append(svc)
            else:
                unavailable.append(svc)
        return {
            "status": "HEALTHY",
            "message": "SharedContext operational.",
            "details": {
                "available_services": available,
                "unavailable_services": unavailable
            }
        }
