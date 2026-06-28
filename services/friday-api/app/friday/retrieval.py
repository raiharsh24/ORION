from typing import List, Dict, Any, Optional
from loguru import logger
from app.friday.vectordb import VectorDB
from app.memory.embeddings import EmbeddingsManager

class RetrievalEngine:
    """
    Performs semantic lookup across indexed documents using calculated query vectors.
    """
    def __init__(self, vector_db: VectorDB, embeddings: EmbeddingsManager) -> None:
        self.vector_db = vector_db
        self.embeddings = embeddings

    async def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Embeds query text, fetches similar documents from VectorDB, and returns structured metadata results.
        """
        if not query.strip():
            return []

        logger.info(f"Executing semantic search query: '{query}'")
        try:
            # Generate query embedding vector
            query_vector = await self.embeddings.embed_text(query)
            
            # Query vector database
            raw_results = self.vector_db.query(
                query_embeddings=[query_vector],
                n_results=n_results
            )

            # Format raw database output
            formatted = []
            ids = raw_results.get("ids", [[]])[0]
            documents = raw_results.get("documents", [[]])[0]
            metadatas = raw_results.get("metadatas", [[]])[0]
            distances = raw_results.get("distances", [[]])[0]

            for idx in range(len(ids)):
                # Return standard dict mapping document text to metadata and score
                formatted.append({
                    "id": ids[idx],
                    "document": documents[idx],
                    "metadata": metadatas[idx],
                    "score": 1.0 - distances[idx] if idx < len(distances) else 0.0
                })
            
            logger.debug(f"Search query returned {len(formatted)} matching document chunks.")
            return formatted
        except Exception as e:
            logger.error(f"Error performing semantic retrieval search: {str(e)}")
            return []
