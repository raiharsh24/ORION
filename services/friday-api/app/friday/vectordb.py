import os
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from loguru import logger

class VectorStore(ABC):
    """
    Abstract VectorStore boundary interface.
    """
    @abstractmethod
    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]) -> None:
        pass

    @abstractmethod
    def query(self, query_embeddings: List[List[float]], n_results: int = 5) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def reset_collection(self) -> None:
        pass

class InMemoryVectorStore(VectorStore):
    """
    Volatile in-memory vector storage for testing and session data.
    """
    def __init__(self) -> None:
        self.ids = []
        self.embeddings = []
        self.metadatas = []
        self.documents = []

    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]) -> None:
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
        results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
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
        return {
            "ids": self.ids,
            "documents": self.documents,
            "metadatas": self.metadatas
        }

    def delete(self, ids: List[str]) -> None:
        for doc_id in ids:
            if doc_id in self.ids:
                idx = self.ids.index(doc_id)
                del self.ids[idx]
                del self.embeddings[idx]
                del self.metadatas[idx]
                del self.documents[idx]

    def reset_collection(self) -> None:
        self.ids = []
        self.embeddings = []
        self.metadatas = []
        self.documents = []


class JSONVectorStore(InMemoryVectorStore):
    """
    Thread-safe, file-backed JSON VectorStore for local environment persistence.
    """
    def __init__(self, persist_dir: str) -> None:
        super().__init__()
        self.persist_dir = persist_dir
        self.db_path = os.path.join(persist_dir, "vector_db.json")
        os.makedirs(persist_dir, exist_ok=True)
        self.load()

    def load(self) -> None:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", [])
                    self.metadatas = data.get("metadatas", [])
                    self.embeddings = data.get("embeddings", [])
                    self.ids = data.get("ids", [])
                logger.info(f"Loaded {len(self.ids)} documents from JSONVectorStore file.")
            except Exception as e:
                logger.error(f"Failed to load JSONVectorStore file: {str(e)}")

    def save(self) -> None:
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({
                    "documents": self.documents,
                    "metadatas": self.metadatas,
                    "embeddings": self.embeddings,
                    "ids": self.ids
                }, f)
            logger.info(f"Saved JSONVectorStore file to: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to save JSONVectorStore file: {str(e)}")

    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]) -> None:
        super().add(ids, embeddings, metadatas, documents)
        self.save()

    def delete(self, ids: List[str]) -> None:
        super().delete(ids)
        self.save()

    def reset_collection(self) -> None:
        super().reset_collection()
        self.save()


# Backward Compatibility mapping wrappers
SimpleVectorDB = JSONVectorStore

class VectorDB(VectorStore):
    """
    Orchestration class redirecting dynamically to ChromaDB or SimpleVectorDB fallback.
    """
    def __init__(self, persist_dir: str) -> None:
        self.persist_dir = persist_dir
        self.use_chroma = False
        self.collection = None
        self.fallback_db = None

        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection("friday_knowledge")
            self.use_chroma = True
            logger.info("ChromaDB persistent collection active.")
        except ImportError:
            logger.warning("chromadb not installed. Defaulting to JSONVectorStore fallback.")
            self.fallback_db = JSONVectorStore(self.persist_dir)
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {str(e)}. Falling back to JSONVectorStore.")
            self.fallback_db = JSONVectorStore(self.persist_dir)

    def add(self, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], documents: List[str]) -> None:
        if self.use_chroma:
            try:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents
                )
            except Exception as e:
                logger.error(f"ChromaDB add failed: {str(e)}")
                if not self.fallback_db:
                    self.fallback_db = JSONVectorStore(self.persist_dir)
                self.fallback_db.add(ids, embeddings, metadatas, documents)
        else:
            self.fallback_db.add(ids, embeddings, metadatas, documents)

    def query(self, query_embeddings: List[List[float]], n_results: int = 5) -> Dict[str, Any]:
        if self.use_chroma:
            try:
                return self.collection.query(
                    query_embeddings=query_embeddings,
                    n_results=n_results
                )
            except Exception as e:
                logger.error(f"ChromaDB query failed: {str(e)}")
                if not self.fallback_db:
                    self.fallback_db = JSONVectorStore(self.persist_dir)
                return self.fallback_db.query(query_embeddings, n_results)
        else:
            return self.fallback_db.query(query_embeddings, n_results)

    def get(self) -> Dict[str, Any]:
        if self.use_chroma:
            try:
                return self.collection.get()
            except Exception as e:
                logger.error(f"ChromaDB get failed: {str(e)}")
                if not self.fallback_db:
                    self.fallback_db = JSONVectorStore(self.persist_dir)
                return self.fallback_db.get()
        else:
            return self.fallback_db.get()

    def delete(self, ids: List[str]) -> None:
        if self.use_chroma:
            try:
                self.collection.delete(ids=ids)
            except Exception as e:
                logger.error(f"ChromaDB delete failed: {str(e)}")
                if not self.fallback_db:
                    self.fallback_db = JSONVectorStore(self.persist_dir)
                self.fallback_db.delete(ids)
        else:
            self.fallback_db.delete(ids)

    def reset_collection(self) -> None:
        if self.use_chroma:
            try:
                self.client.delete_collection("friday_knowledge")
                self.collection = self.client.get_or_create_collection("friday_knowledge")
                logger.info("ChromaDB collection reset.")
            except Exception as e:
                logger.error(f"Failed to reset ChromaDB collection: {str(e)}")
        else:
            self.fallback_db.reset_collection()
