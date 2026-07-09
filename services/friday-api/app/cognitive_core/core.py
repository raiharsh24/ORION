from typing import Optional, Dict, Any
from loguru import logger

from app.cognitive_core.planner import UnifiedPlanner
from app.cognitive_core.graph import CognitiveGraph


class CognitiveCore:
    def __init__(
        self,
        event_bus: Optional[Any] = None,
        planning_engine: Optional[Any] = None,
        universal_tool_registry: Optional[Any] = None,
        memory_retriever: Optional[Any] = None,
        semantic_store: Optional[Any] = None,
        knowledge_graph: Optional[Any] = None,
        atlas_store: Optional[Any] = None,
    ) -> None:
        self._event_bus = event_bus

        self.planner = UnifiedPlanner(
            event_bus=event_bus,
            planning_engine=planning_engine,
            tool_registry=universal_tool_registry,
        )

        self.graph = CognitiveGraph(
            knowledge_graph=knowledge_graph,
            atlas_store=atlas_store,
        )

        self._memory_retriever = memory_retriever
        self._semantic_store = semantic_store
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        if self._event_bus:
            self.planner.set_event_bus(self._event_bus)

        self._initialized = True
        logger.info("CognitiveCore initialized")

    async def process_with_cognition(
        self,
        prompt: str,
        use_cognitive_planning: bool = False,
    ) -> Dict[str, Any]:
        plan = await self.planner.plan(
            prompt=prompt,
            use_cognitive=use_cognitive_planning,
        )

        graph_ctx = self.graph.graph_context(prompt, max_entities=5)

        semantic_ctx = ""
        if self._semantic_store:
            try:
                results = self._semantic_store.search(prompt, top_k=3)
                if results:
                    semantic_ctx = "\n".join(
                        f"  - {r['text'][:200]}" for r in results
                    )
            except Exception as e:
                logger.debug(f"CognitiveCore semantic search skipped: {e}")

        return {
            "plan": plan,
            "graph_context": graph_ctx,
            "semantic_context": semantic_ctx,
        }

    async def retrieve_relevant_context(
        self,
        query: str,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        semantic_chunks: list = []
        if self._semantic_store:
            try:
                semantic_chunks = self._semantic_store.search(query, top_k=top_k)
            except Exception as e:
                logger.debug(f"CognitiveCore semantic retrieval skipped: {e}")

        graph_ctx = self.graph.graph_context(query, max_entities=top_k)

        memory_chunks: list = []
        if self._memory_retriever:
            try:
                memory_chunks = self._memory_retriever.retrieve(
                    query=query,
                    top_k=top_k,
                )
            except Exception as e:
                logger.debug(f"CognitiveCore memory retrieval skipped: {e}")

        combined: list = []
        seen_texts: set = set()

        for r in semantic_chunks:
            text = r.get("text", "")[:200]
            if text and text not in seen_texts:
                combined.append(f"[Semantic] {text}")
                seen_texts.add(text)

        for r in memory_chunks:
            text = r.get("text", "") if isinstance(r, dict) else str(r)[:200]
            if text and text not in seen_texts:
                combined.append(f"[Memory] {text}")
                seen_texts.add(text)

        return {
            "semantic_results": semantic_chunks,
            "memory_results": memory_chunks,
            "graph_context": graph_ctx,
            "combined_context": "\n".join(combined[:top_k * 2]) if combined else "",
            "result_count": len(combined),
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "planner": self.planner.health(),
            "graph_entities": self.graph.stats().get("knowledge_graph", {}).get("entity_count", 0),
            "initialized": self._initialized,
        }
