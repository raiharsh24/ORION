import os
import json
from loguru import logger

class SimpleVectorDB:
    """
    Fallback local vector database with cosine similarity search and JSON serialization.
    Ensures 100% reliable local search without compilation dependencies.
    """
    def __init__(self, persist_dir: str) -> None:
        self.persist_dir = persist_dir
        self.db_path = os.path.join(persist_dir, "vector_db.json")
        self.documents = []
        self.metadatas = []
        self.embeddings = []
        self.ids = []
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
                logger.info(f"Loaded {len(self.ids)} documents from SimpleVectorDB file.")
            except Exception as e:
                logger.error(f"Failed to load local vector file: {str(e)}")

    def save(self) -> None:
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({
                    "documents": self.documents,
                    "metadatas": self.metadatas,
                    "embeddings": self.embeddings,
                    "ids": self.ids
                }, f)
            logger.info(f"Saved SimpleVectorDB file to: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to save local vector database: {str(e)}")

    def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict], documents: list[str]) -> None:
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
        self.save()

    def query(self, query_embeddings: list[list[float]], n_results: int = 5) -> dict:
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

        # Sort descending by similarity
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_k = similarities[:n_results]

        for sim, idx in top_k:
            results["ids"][0].append(self.ids[idx])
            results["documents"][0].append(self.documents[idx])
            results["metadatas"][0].append(self.metadatas[idx])
            results["distances"][0].append(1.0 - sim)  # distance = 1 - cosine_similarity

        return results

    def get(self) -> dict:
        return {
            "ids": self.ids,
            "documents": self.documents,
            "metadatas": self.metadatas
        }

    def delete(self, ids: list[str]) -> None:
        new_ids = []
        new_documents = []
        new_metadatas = []
        new_embeddings = []
        for i, doc_id in enumerate(self.ids):
            if doc_id not in ids:
                new_ids.append(doc_id)
                new_documents.append(self.documents[i])
                new_metadatas.append(self.metadatas[i])
                new_embeddings.append(self.embeddings[i])
        self.ids = new_ids
        self.documents = new_documents
        self.metadatas = new_metadatas
        self.embeddings = new_embeddings
        self.save()


class VectorDB:
    """
    Abstration class that utilizes ChromaDB if installed, otherwise falling back
    transparently to SimpleVectorDB for system integrity.
    """
    def __init__(self, persist_dir: str) -> None:
        self.persist_dir = persist_dir
        self.use_chroma = False
        self.collection = None
        self.fallback_db = None

        try:
            import chromadb
            # Try initializing chromadb PersistentClient
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection("orion_knowledge")
            self.use_chroma = True
            logger.info("ChromaDB persistent collection active.")
        except ImportError:
            logger.warning("chromadb not installed. Defaulting to SimpleVectorDB fallback.")
            self.fallback_db = SimpleVectorDB(self.persist_dir)
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {str(e)}. Falling back to SimpleVectorDB.")
            self.fallback_db = SimpleVectorDB(self.persist_dir)

    def add(self, ids: list[str], embeddings: list[list[float]], metadatas: list[dict], documents: list[str]) -> None:
        if self.use_chroma:
            try:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents
                )
            except Exception as e:
                logger.error(f"ChromaDB add failed, retrying on fallback: {str(e)}")
                if not self.fallback_db:
                    self.fallback_db = SimpleVectorDB(self.persist_dir)
                self.fallback_db.add(ids, embeddings, metadatas, documents)
        else:
            self.fallback_db.add(ids, embeddings, metadatas, documents)

    def query(self, query_embeddings: list[list[float]], n_results: int = 5) -> dict:
        if self.use_chroma:
            try:
                return self.collection.query(
                    query_embeddings=query_embeddings,
                    n_results=n_results
                )
            except Exception as e:
                logger.error(f"ChromaDB query failed: {str(e)}. Falling back.")
                if not self.fallback_db:
                    self.fallback_db = SimpleVectorDB(self.persist_dir)
                return self.fallback_db.query(query_embeddings, n_results)
        else:
            return self.fallback_db.query(query_embeddings, n_results)

    def get(self) -> dict:
        if self.use_chroma:
            try:
                return self.collection.get()
            except Exception as e:
                logger.error(f"ChromaDB get failed: {str(e)}. Falling back.")
                if not self.fallback_db:
                    self.fallback_db = SimpleVectorDB(self.persist_dir)
                return self.fallback_db.get()
        else:
            return self.fallback_db.get()

    def reset_collection(self) -> None:
        if self.use_chroma:
            try:
                self.client.delete_collection("orion_knowledge")
                self.collection = self.client.get_or_create_collection("orion_knowledge")
                logger.info("ChromaDB collection reset.")
            except Exception as e:
                logger.error(f"Failed to reset ChromaDB collection: {str(e)}")
        else:
            self.fallback_db.delete(self.fallback_db.ids)
            logger.info("SimpleVectorDB collection reset.")
