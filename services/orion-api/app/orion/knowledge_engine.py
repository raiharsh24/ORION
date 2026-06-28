import time
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from app.orion.vectordb import VectorStore, VectorDB
from app.orion.knowledge_embeddings import EmbeddingProvider, GeminiEmbeddingProvider
from app.orion.knowledge_document import Document, DocumentParser, ChunkManager
from app.orion.knowledge_retriever import SemanticRetriever, HybridRetriever, KnowledgeRanker
from app.orion.knowledge_context import CitationManager, ContextAssembler
from app.events.events import OrionEvent

# Event models
class DocumentIndexed(OrionEvent):
    def __init__(self, doc_id: str, chunks_count: int) -> None:
        super().__init__(topic="DocumentIndexed", data={"document_id": doc_id, "chunks_count": chunks_count})

class DocumentUpdated(OrionEvent):
    def __init__(self, doc_id: str) -> None:
        super().__init__(topic="DocumentUpdated", data={"document_id": doc_id})

class DocumentDeleted(OrionEvent):
    def __init__(self, doc_id: str) -> None:
        super().__init__(topic="DocumentDeleted", data={"document_id": doc_id})

class EmbeddingGenerated(OrionEvent):
    def __init__(self, text: str) -> None:
        super().__init__(topic="EmbeddingGenerated", data={"text_length": len(text)})

class KnowledgeRetrieved(OrionEvent):
    def __init__(self, query: str, results_count: int) -> None:
        super().__init__(topic="KnowledgeRetrieved", data={"query": query, "results_count": results_count})

class KnowledgeFailed(OrionEvent):
    def __init__(self, query: str, error: str) -> None:
        super().__init__(topic="KnowledgeFailed", data={"query": query, "error": error})


class KnowledgeManager:
    """
    Orchestrates parsing, chunk splitters, embedding vector lookups, and hybrid queries.
    """
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        event_bus: Optional[Any] = None
    ) -> None:
        self._store = vector_store
        self._provider = embedding_provider
        self._event_bus = event_bus

        self.parser = DocumentParser()
        self.chunk_manager = ChunkManager()
        self.semantic_retriever = SemanticRetriever(self._store, self._provider)
        self.hybrid_retriever = HybridRetriever(self.semantic_retriever)
        self.ranker = KnowledgeRanker()
        self.citation_manager = CitationManager()
        self.context_assembler = ContextAssembler(self.citation_manager)

        # Telemetry metrics
        self.documents_indexed = 0
        self.chunks_count = 0
        self.embeddings_count = 0
        self.retrieval_latency_sum = 0.0
        self.retrieval_count = 0
        self.index_latency_sum = 0.0
        self.index_count = 0

    def _safe_publish(self, event: OrionEvent) -> None:
        if not self._event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self._event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    asyncio.run(self._event_bus.publish(event))
            else:
                self._event_bus.publish(event)
        except Exception as e:
            logger.error(f"Failed to publish event: {str(e)}")

    async def index_file(self, file_path: str, chunk_size: int = 500) -> None:
        start_time = time.time()
        self.index_count += 1

        try:
            doc = self.parser.parse_file(file_path)
            chunks = self.chunk_manager.chunk_document(doc, strategy="Fixed", chunk_size=chunk_size)

            ids = []
            embeddings = []
            metadatas = []
            documents_text = []

            for chunk in chunks:
                emb = await self._provider.embed_text(chunk.text)
                self.embeddings_count += 1
                self._safe_publish(EmbeddingGenerated(text=chunk.text))

                ids.append(chunk.id)
                embeddings.append(emb)
                metadatas.append(chunk.metadata.model_dump())
                documents_text.append(chunk.text)

            self._store.add(ids, embeddings, metadatas, documents_text)
            self.documents_indexed += 1
            self.chunks_count += len(chunks)

            self._safe_publish(DocumentIndexed(doc_id=file_path, chunks_count=len(chunks)))
            self.index_latency_sum += (time.time() - start_time) * 1000.0

        except Exception as e:
            logger.error(f"KnowledgeManager indexing failed for '{file_path}': {str(e)}")
            raise e

    async def delete_document(self, file_path: str) -> None:
        try:
            all_data = self._store.get()
            ids_to_delete = []
            for idx, m in enumerate(all_data.get("metadatas", [])):
                if m.get("document_id") == file_path or m.get("path") == file_path:
                    ids_to_delete.append(all_data["ids"][idx])

            if ids_to_delete:
                self._store.delete(ids_to_delete)
            else:
                logger.warning(f"No indexed chunks found for document '{file_path}'")

            self.documents_indexed = max(0, self.documents_indexed - 1)
            self.chunks_count = max(0, self.chunks_count - len(ids_to_delete))
            self._safe_publish(DocumentDeleted(doc_id=file_path))
        except AttributeError:
            logger.warning("VectorStore does not support delete(). Resetting collection as fallback.")
            self._store.reset_collection()
            self.documents_indexed = 0
            self.chunks_count = 0
        except Exception as e:
            logger.error(f"Failed to delete document '{file_path}': {str(e)}")

    async def query_knowledge(
        self,
        query: str,
        n_results: int = 5,
        alpha: float = 0.5,
        threshold: float = 0.1
    ) -> Dict[str, Any]:
        start_time = time.time()
        self.retrieval_count += 1

        try:
            candidates = await self.hybrid_retriever.retrieve(query, n_results=n_results, alpha=alpha)
            ranked = self.ranker.rank_and_filter(candidates, threshold=threshold, top_k=n_results)
            assembled = self.context_assembler.assemble_context(ranked)

            self._safe_publish(KnowledgeRetrieved(query=query, results_count=len(ranked)))
            self.retrieval_latency_sum += (time.time() - start_time) * 1000.0

            return assembled
        except Exception as e:
            self._safe_publish(KnowledgeFailed(query=query, error=str(e)))
            raise e


class KnowledgeEngine:
    """
    Main KnowledgeEngine service subsystem container.
    Exposes backwards compatible semantic query search methods.
    """
    def __init__(self) -> None:
        self._manager: Optional[KnowledgeManager] = None
        self._initialized = False
        self._persist_dir: Optional[str] = None

    async def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("Initializing KnowledgeEngine service...")
        from app.kernel.kernel import OrionKernel
        kernel = OrionKernel.get_instance()
        event_bus = kernel.get_service("event_bus")

        self._persist_dir = kernel._config.paths.persist_dir
        store = VectorDB(persist_dir=self._persist_dir)
        provider = GeminiEmbeddingProvider()

        self._manager = KnowledgeManager(
            vector_store=store,
            embedding_provider=provider,
            event_bus=event_bus
        )

        if event_bus:
            event_bus.subscribe("MemoryUpdated", self.on_memory_updated)
            event_bus.subscribe("ToolCompleted", self.on_tool_completed)
            event_bus.subscribe("MissionCompleted", self.on_mission_completed)
            event_bus.subscribe("WorkflowCompleted", self.on_workflow_completed)

        self._initialized = True
        logger.info("KnowledgeEngine initialized successfully.")

    async def start(self) -> None:
        logger.info("KnowledgeEngine service started.")

    async def shutdown(self) -> None:
        logger.info("KnowledgeEngine service shut down.")

    def health(self) -> Dict[str, Any]:
        if not self._initialized or not self._manager:
            return {"status": "WARNING", "message": "KnowledgeEngine not initialized."}

        avg_retrieval_lat = 0.0
        if self._manager.retrieval_count > 0:
            avg_retrieval_lat = self._manager.retrieval_latency_sum / self._manager.retrieval_count

        avg_index_lat = 0.0
        if self._manager.index_count > 0:
            avg_index_lat = self._manager.index_latency_sum / self._manager.index_count

        return {
            "status": "HEALTHY",
            "message": "KnowledgeEngine operating nominally.",
            "details": {
                "documents_indexed": self._manager.documents_indexed,
                "chunks_count": self._manager.chunks_count,
                "embeddings_count": self._manager.embeddings_count,
                "retrieval_latency_ms": round(avg_retrieval_lat, 2),
                "index_latency_ms": round(avg_index_lat, 2)
            }
        }

    # ==========================================
    # Backward Compatibility Mappings
    # ==========================================
    async def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        if not self._manager:
            logger.warning("KnowledgeEngine.search called before initialize. Using fallback.")
            from app.orion.vectordb import JSONVectorStore
            persist_dir = self._persist_dir or ".orion_kb"
            store = JSONVectorStore(persist_dir=persist_dir)
            provider = GeminiEmbeddingProvider()
            self._manager = KnowledgeManager(store, provider, None)

        candidates = await self._manager.hybrid_retriever.retrieve(query, n_results=n_results)

        formatted = []
        for c in candidates[:n_results]:
            formatted.append({
                "id": c["id"],
                "document": c["text"],
                "metadata": c["metadata"],
                "score": c["score"]
            })
        return formatted

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Workflow-compatible retrieval interface.
        Delegates to search() for backward-compatible result format.
        """
        return await self.search(query, n_results=top_k)

    # EventBus subscription hook callbacks
    def on_memory_updated(self, event: OrionEvent) -> None:
        data = event.data if isinstance(event.data, dict) else {}
        content = data.get("content", "") or str(data)
        logger.info(f"KnowledgeEngine: MemoryUpdated event received ({len(content)} chars)")
        if self._manager and content:
            logger.debug("KnowledgeEngine: Memory content available for potential indexing")

    def on_tool_completed(self, event: OrionEvent) -> None:
        data = event.data if isinstance(event.data, dict) else {}
        output = data.get("output") or data.get("result")
        tool_name = data.get("tool", "unknown")
        logger.info(f"KnowledgeEngine: ToolCompleted event received (tool={tool_name})")
        if output and self._manager:
            logger.debug("KnowledgeEngine: Tool output available for knowledge extraction")

    def on_mission_completed(self, event: OrionEvent) -> None:
        data = event.data if isinstance(event.data, dict) else {}
        mission_id = data.get("mission_id", "unknown")
        logger.info(f"KnowledgeEngine: MissionCompleted event received (mission_id={mission_id})")
        if self._manager:
            logger.info(f"KnowledgeEngine: Scheduling workspace re-index opportunity after mission {mission_id}")

    def on_workflow_completed(self, event: OrionEvent) -> None:
        data = event.data if isinstance(event.data, dict) else {}
        workflow_id = data.get("workflow_id", "unknown")
        logger.info(f"KnowledgeEngine: WorkflowCompleted event received (workflow_id={workflow_id})")
        if self._manager:
            logger.info("KnowledgeEngine: Scheduling workspace re-index opportunity after workflow completion")
