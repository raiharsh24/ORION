from typing import Dict, Any, List, Tuple
from app.orion.vectordb import VectorStore
from app.orion.knowledge_embeddings import EmbeddingProvider

class SemanticRetriever:
    """
    Performs vector similarity lookup using Embedding providers.
    """
    def __init__(self, vector_store: VectorStore, embedding_provider: EmbeddingProvider) -> None:
        self._store = vector_store
        self._provider = embedding_provider

    async def retrieve_semantic(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        query_vector = await self._provider.embed_text(query)
        raw_res = self._store.query([query_vector], n_results)

        formatted = []
        ids = raw_res.get("ids", [[]])[0]
        documents = raw_res.get("documents", [[]])[0]
        metadatas = raw_res.get("metadatas", [[]])[0]
        distances = raw_res.get("distances", [[]])[0]

        for idx in range(len(ids)):
            score = 1.0 - distances[idx] if idx < len(distances) else 0.0
            formatted.append({
                "id": ids[idx],
                "text": documents[idx],
                "metadata": metadatas[idx],
                "score": score
            })
        return formatted

class HybridRetriever:
    """
    Integrates semantic cosine vectors with keyword overlap ratio matching.
    """
    def __init__(self, semantic_retriever: SemanticRetriever) -> None:
        self._semantic = semantic_retriever

    async def retrieve(
        self,
        query: str,
        n_results: int = 5,
        alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        # Fetch candidate pool
        semantic_results = await self._semantic.retrieve_semantic(query, n_results=n_results * 2)
        if not semantic_results:
            return []

        query_tokens = set(query.lower().split())
        if not query_tokens:
            return semantic_results[:n_results]

        hybrid_results = []
        for item in semantic_results:
            text_tokens = set(item["text"].lower().split())
            intersection = query_tokens.intersection(text_tokens)
            keyword_score = len(intersection) / len(query_tokens)

            combined_score = alpha * item["score"] + (1.0 - alpha) * keyword_score
            item["score"] = combined_score
            hybrid_results.append(item)

        return hybrid_results

class KnowledgeRanker:
    """
    Applies score thresholds and enforces Top-K constraints.
    """
    def rank_and_filter(
        self,
        results: List[Dict[str, Any]],
        threshold: float = 0.1,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        sorted_res = sorted(results, key=lambda x: x["score"], reverse=True)
        filtered = [x for x in sorted_res if x["score"] >= threshold]
        return filtered[:top_k]
