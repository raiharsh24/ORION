from typing import Dict, Any, List, Optional
from threading import Lock
from loguru import logger

from app.memory.schema import MemoryEntry
from app.memory.embeddings import EmbeddingsManager


class InMemoryVectorStore:
    """Thread-safe in-memory vector storage for fallback when Chroma is unavailable."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.ids: List[str] = []
        self.embeddings: List[List[float]] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.documents: List[str] = []

    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]) -> None:
        with self._lock:
            for idx, doc_id in enumerate(ids):
                if doc_id in self.ids:
                    i = self.ids.index(doc_id)
                    self.embeddings[i] = embeddings[idx]
                    self.metadatas[i] = metadatas[idx]
                    self.documents[i] = documents[idx]
                else:
                    self.ids.append(doc_id)
                    self.embeddings.append(embeddings[idx])
                    self.metadatas.append(metadatas[idx])
                    self.documents.append(documents[idx])

    def query(self, query_embeddings: List[List[float]], n_results: int = 5) -> Dict[str, Any]:
        results: Dict[str, Any] = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        with self._lock:
            if not self.embeddings or not query_embeddings:
                return results
            q_emb = query_embeddings[0]
            similarities = []
            for i, emb in enumerate(self.embeddings):
                dot = sum(a * b for a, b in zip(q_emb, emb))
                norm_a = sum(a * a for a in q_emb) ** 0.5
                norm_b = sum(b * b for b in emb) ** 0.5
                similarity = dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
                similarities.append((similarity, i))
            similarities.sort(key=lambda x: x[0], reverse=True)
            top_k = similarities[:n_results]
            for sim, idx in top_k:
                results["ids"][0].append(self.ids[idx])
                results["documents"][0].append(self.documents[idx])
                results["metadatas"][0].append(self.metadatas[idx])
                results["distances"][0].append(1.0 - sim)
        return results

    def get(self) -> Dict[str, Any]:
        with self._lock:
            return {"ids": list(self.ids), "documents": list(self.documents), "metadatas": list(self.metadatas)}

    def delete(self, ids: List[str]) -> None:
        with self._lock:
            for doc_id in ids:
                if doc_id in self.ids:
                    idx = self.ids.index(doc_id)
                    del self.ids[idx]
                    del self.embeddings[idx]
                    del self.metadatas[idx]
                    del self.documents[idx]

    def reset_collection(self) -> None:
        with self._lock:
            self.ids = []
            self.embeddings = []
            self.metadatas = []
            self.documents = []


class SemanticMemoryStore:
    """
    Stores memory entries as vector embeddings in a dedicated Chroma collection
    ('friday_memory') for semantic similarity retrieval.

    Connects the EmbeddingsManager (memory/embeddings.py) to persistent
    vector storage, enabling semantic search across session, user, project,
    and episodic memories. Falls back to an in-memory vector store when
    ChromaDB is unavailable.
    """

    def __init__(self, persist_dir: str) -> None:
        self._persist_dir = persist_dir
        self._embedder = EmbeddingsManager()
        self._use_chroma = False
        self._collection = None
        self._fallback: Optional[InMemoryVectorStore] = None
        self._init_store()

    def _init_store(self) -> None:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection = client.get_or_create_collection("friday_memory")
            self._use_chroma = True
            logger.info("SemanticMemoryStore: ChromaDB 'friday_memory' collection ready.")
        except ImportError:
            logger.warning("chromadb not installed. SemanticMemoryStore using in-memory fallback.")
            self._fallback = InMemoryVectorStore()
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}. SemanticMemoryStore using in-memory fallback.")
            self._fallback = InMemoryVectorStore()

    async def _get_embedding(self, text: str) -> List[float]:
        return await self._embedder.embed_text(text)

    def _get_mock_embedding(self, text: str) -> List[float]:
        """Sync deterministic embedding using the manager's mock fallback."""
        return self._embedder._get_mock_embedding(text)

    async def store_memory(self, entry: MemoryEntry) -> None:
        """Embed a single MemoryEntry and upsert into the vector store."""
        embedding = await self._get_embedding(entry.content)
        metadata = dict(entry.metadata) if entry.metadata else {}
        metadata.update({
            "memory_id": entry.id,
            "category": entry.category,
            "importance": entry.importance,
            "timestamp": entry.timestamp,
        })
        if self._use_chroma:
            try:
                self._collection.add(
                    ids=[entry.id],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    documents=[entry.content],
                )
            except Exception as e:
                logger.error(f"ChromaDB store_memory failed: {e}")
        elif self._fallback:
            self._fallback.add(
                ids=[entry.id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[entry.content],
            )

    async def store_memories(self, entries: List[MemoryEntry]) -> None:
        """Batch embed and store multiple memory entries."""
        if not entries:
            return
        ids: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []
        documents: List[str] = []
        for entry in entries:
            embedding = await self._get_embedding(entry.content)
            metadata = dict(entry.metadata) if entry.metadata else {}
            metadata.update({
                "memory_id": entry.id,
                "category": entry.category,
                "importance": entry.importance,
                "timestamp": entry.timestamp,
            })
            ids.append(entry.id)
            embeddings.append(embedding)
            metadatas.append(metadata)
            documents.append(entry.content)
        if self._use_chroma:
            try:
                self._collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
                logger.debug(f"Stored {len(ids)} memories in Chroma 'friday_memory'.")
            except Exception as e:
                logger.error(f"ChromaDB batch store_memories failed: {e}")
        elif self._fallback:
            self._fallback.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    async def delete_memory(self, memory_id: str) -> None:
        """Remove a memory entry from the vector store."""
        self._delete_memory_sync(memory_id)

    def delete_memory_sync(self, memory_id: str) -> None:
        """Synchronous version of delete_memory."""
        self._delete_memory_sync(memory_id)

    def _delete_memory_sync(self, memory_id: str) -> None:
        if self._use_chroma:
            try:
                self._collection.delete(ids=[memory_id])
            except Exception as e:
                logger.debug(f"ChromaDB delete_memory ({memory_id}): {e}")
        elif self._fallback:
            self._fallback.delete([memory_id])

    async def query(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Query the vector store by semantic similarity.

        Returns a list of dicts with keys: id, memory_id, text, metadata, score.
        Empty list if the store has no entries.
        """
        query_vector = await self._get_embedding(query)
        if self._use_chroma:
            try:
                raw = self._collection.query(
                    query_embeddings=[query_vector],
                    n_results=n_results,
                )
            except Exception as e:
                logger.error(f"ChromaDB query failed: {e}")
                return []
        elif self._fallback:
            raw = self._fallback.query([query_vector], n_results)
        else:
            return []

        ids = raw.get("ids", [[]])[0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        results = []
        for idx in range(len(ids)):
            score = 1.0 - distances[idx] if idx < len(distances) else 0.0
            meta = metadatas[idx] if idx < len(metadatas) else {}
            results.append({
                "id": ids[idx],
                "memory_id": meta.get("memory_id", ids[idx]),
                "text": documents[idx] if idx < len(documents) else "",
                "metadata": meta,
                "score": round(score, 4),
            })
        return results

    async def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all entries from the semantic store (for inspection)."""
        return self._get_all_sync()

    def get_all_sync(self) -> List[Dict[str, Any]]:
        """Synchronous version of get_all for use in sync contexts and tests."""
        return self._get_all_sync()

    def _get_all_sync(self) -> List[Dict[str, Any]]:
        if self._use_chroma:
            try:
                raw = self._collection.get()
            except Exception as e:
                logger.error(f"ChromaDB get_all failed: {e}")
                return []
        elif self._fallback:
            raw = self._fallback.get()
        else:
            return []
        ids = raw.get("ids", [])
        documents = raw.get("documents", [])
        metadatas = raw.get("metadatas", [])
        return [
            {"id": ids[i], "text": documents[i], "metadata": metadatas[i]}
            for i in range(len(ids))
        ]

    def store_memory_sync(self, entry: MemoryEntry) -> None:
        """Synchronous store using deterministic mock embedding (no API call)."""
        embedding = self._get_mock_embedding(entry.content)
        metadata = dict(entry.metadata) if entry.metadata else {}
        metadata.update({
            "memory_id": entry.id,
            "category": entry.category,
            "importance": entry.importance,
            "timestamp": entry.timestamp,
        })
        if self._use_chroma:
            try:
                self._collection.add(
                    ids=[entry.id],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    documents=[entry.content],
                )
            except Exception as e:
                logger.error(f"ChromaDB store_memory_sync failed: {e}")
        elif self._fallback:
            self._fallback.add(
                ids=[entry.id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[entry.content],
            )

    def store_memories_sync(self, entries: List[MemoryEntry]) -> None:
        """Batch sync store using deterministic mock embeddings."""
        if not entries:
            return
        ids: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []
        documents: List[str] = []
        for entry in entries:
            embedding = self._get_mock_embedding(entry.content)
            metadata = dict(entry.metadata) if entry.metadata else {}
            metadata.update({
                "memory_id": entry.id,
                "category": entry.category,
                "importance": entry.importance,
                "timestamp": entry.timestamp,
            })
            ids.append(entry.id)
            embeddings.append(embedding)
            metadatas.append(metadata)
            documents.append(entry.content)
        if self._use_chroma:
            try:
                self._collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
            except Exception as e:
                logger.error(f"ChromaDB batch store_memories_sync failed: {e}")
        elif self._fallback:
            self._fallback.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

    def health(self) -> Dict[str, Any]:
        """Expose health status for the subsystem health monitor."""
        return {
            "status": "HEALTHY" if self._use_chroma or self._fallback else "ERROR",
            "backend": "chromadb" if self._use_chroma else "in_memory",
        }
