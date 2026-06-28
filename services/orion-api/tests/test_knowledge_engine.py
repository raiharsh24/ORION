import pytest
import anyio
import os
import tempfile
from typing import Dict, Any

from app.orion.vectordb import InMemoryVectorStore, JSONVectorStore, VectorDB
from app.orion.knowledge_embeddings import GeminiEmbeddingProvider, LocalEmbeddingProvider
from app.orion.knowledge_document import Document, DocumentParser, ChunkManager
from app.orion.knowledge_retriever import SemanticRetriever, HybridRetriever, KnowledgeRanker
from app.orion.knowledge_context import CitationManager, ContextAssembler
from app.orion.knowledge_engine import KnowledgeEngine, KnowledgeManager
from app.events.bus import EventBus
from app.kernel import OrionKernel, OrionKernelConfig

# ----------------------------------------------------
# 1. Pipeline Components Unit Tests
# ----------------------------------------------------
def test_document_parser_and_chunker():
    parser = DocumentParser()
    chunker = ChunkManager()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmpf:
        tmpf.write(b"Line one of test text.\n\nLine two of test text.")
        tmp_name = tmpf.name
        
    try:
        doc = parser.parse_file(tmp_name)
        assert doc.id == tmp_name
        assert "Line one" in doc.content
        
        # Test Fixed Chunk Strategy
        chunks_fixed = chunker.chunk_document(doc, strategy="Fixed", chunk_size=20)
        assert len(chunks_fixed) > 1
        assert chunks_fixed[0].metadata.document_id == tmp_name
        
        # Test Sliding Window Strategy
        chunks_slide = chunker.chunk_document(doc, strategy="Sliding Window", chunk_size=30, overlap=10)
        assert len(chunks_slide) > 0
    finally:
        os.remove(tmp_name)

def test_vector_store_operations():
    store = InMemoryVectorStore()
    
    ids = ["doc1", "doc2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    metadatas = [{"title": "t1"}, {"title": "t2"}]
    documents = ["hello alpha", "hello beta"]
    
    store.add(ids, embeddings, metadatas, documents)
    assert len(store.get()["ids"]) == 2
    
    # Query check
    res = store.query([[0.1, 0.2]], n_results=1)
    assert res["ids"][0][0] == "doc1"
    assert res["distances"][0][0] == pytest.approx(0.0, abs=1e-5) # distance = 1 - sim = 0

@pytest.mark.anyio
async def test_retrieval_ranking_context():
    store = InMemoryVectorStore()
    provider = LocalEmbeddingProvider()
    
    ids = ["doc1", "doc2"]
    # Generate vectors matching local embedding hash dimension (768)
    v1 = await provider.embed_text("python language tutorial")
    v2 = await provider.embed_text("recipe for chocolate cake")
    
    store.add(ids, [v1, v2], [{"title": "python"}, {"title": "cake"}], ["python language tutorial", "recipe for chocolate cake"])
    
    sem = SemanticRetriever(store, provider)
    hybrid = HybridRetriever(sem)
    ranker = KnowledgeRanker()
    context = ContextAssembler(CitationManager())
    
    # 1. Test Semantic Search
    res_sem = await sem.retrieve_semantic("python programming", n_results=1)
    assert len(res_sem) == 1
    assert res_sem[0]["id"] == "doc1"
    
    # 2. Test Hybrid Retrieval
    res_hyb = await hybrid.retrieve("python tutorial", n_results=2)
    assert len(res_hyb) == 2
    
    # 3. Test Ranker Filter
    res_ranked = ranker.rank_and_filter(res_hyb, threshold=0.1, top_k=1)
    assert len(res_ranked) == 1
    assert res_ranked[0]["id"] == "doc1"
    
    # 4. Test Context Assembler
    res_context = context.assemble_context(res_ranked)
    assert "context_text" in res_context
    assert "<KnowledgeSource" in res_context["context_text"]
    assert len(res_context["citations"]) == 1

@pytest.mark.anyio
async def test_vector_store_delete():
    store = InMemoryVectorStore()

    ids = ["doc1", "doc2", "doc3"]
    embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    metadatas = [{"title": "t1"}, {"title": "t2"}, {"title": "t3"}]
    documents = ["alpha", "beta", "gamma"]

    store.add(ids, embeddings, metadatas, documents)
    assert len(store.get()["ids"]) == 3

    # Delete single document
    store.delete(["doc1"])
    remaining = store.get()
    assert len(remaining["ids"]) == 2
    assert "doc1" not in remaining["ids"]

    # Delete multiple documents
    store.delete(["doc2", "doc3"])
    assert len(store.get()["ids"]) == 0


@ pytest.mark.anyio
async def test_knowledge_engine_retrieve():
    OrionKernel.reset_instance()
    kernel = OrionKernel.get_instance(OrionKernelConfig())
    await kernel.boot()

    engine = kernel.get_service("knowledge_engine")

    # Index a document first
    persist_dir = kernel._config.paths.persist_dir
    test_file = os.path.join(persist_dir, "retrieve_test.txt")
    with open(test_file, "w") as f:
        f.write("Asynchronous programming in Python uses async and await keywords.")

    try:
        await engine._manager.index_file(test_file, chunk_size=100)

        # Test retrieve() method (workflow-compatible interface)
        results = await engine.retrieve("python async", top_k=1)
        assert len(results) == 1
        assert results[0]["score"] > 0.0
        assert "async" in results[0]["document"].lower()
    finally:
        await engine._manager.delete_document(test_file)
        if os.path.exists(test_file):
            os.remove(test_file)

    await kernel.shutdown()


# ----------------------------------------------------
# 2. Boot Sequence Subsystem Integration Tests
# ----------------------------------------------------
@pytest.mark.anyio
async def test_knowledge_engine_integration_events():
    OrionKernel.reset_instance()
    kernel = OrionKernel.get_instance(OrionKernelConfig())
    await kernel.boot()
    
    engine = kernel.get_service("knowledge_engine")
    assert engine is not None
    assert isinstance(engine, KnowledgeEngine)
    
    # Subscribed event logs verification
    event_bus = kernel.get_service("event_bus")
    events = []
    event_bus.subscribe("DocumentIndexed", lambda e: events.append(e))
    event_bus.subscribe("EmbeddingGenerated", lambda e: events.append(e))
    event_bus.subscribe("KnowledgeRetrieved", lambda e: events.append(e))
    
    # Write temp file in workspace to index
    persist_dir = kernel._config.paths.persist_dir
    test_file = os.path.join(persist_dir, "rag_source.txt")
    with open(test_file, "w") as f:
        f.write("FastAPI is an async python web framework.")
        
    try:
        # Index document
        await engine._manager.index_file(test_file, chunk_size=100)
        assert engine._manager.documents_indexed == 1
        assert engine._manager.chunks_count == 1
        
        # Search it (using legacy compatible adapter)
        res = await engine.search("FastAPI python framework", n_results=1)
        assert len(res) == 1
        assert "FastAPI" in res[0]["document"]
        assert res[0]["score"] > 0.0
        
        # Verify event bus triggers
        await anyio.sleep(0.1)
        topics = [e.topic for e in events]
        assert "DocumentIndexed" in topics
        assert "EmbeddingGenerated" in topics
        
    finally:
        # Clean up
        await engine._manager.delete_document(test_file)
        if os.path.exists(test_file):
            os.remove(test_file)
            
    await kernel.shutdown()
