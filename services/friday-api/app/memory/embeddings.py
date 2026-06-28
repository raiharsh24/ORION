import hashlib
from loguru import logger
from app.core.config import settings

class EmbeddingsManager:
    """
    Manages semantic text embeddings. Calls Google's Generative AI API if configured,
    and falls back to deterministic word-hash TF-IDF approximation offline.
    """
    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            logger.info("EmbeddingsManager initialized with Google Generative AI API.")
        else:
            logger.info("EmbeddingsManager initialized in mock/offline fallback mode.")

    def _get_mock_embedding(self, text: str, dimension: int = 768) -> list[float]:
        """
        Calculates a deterministic 768-dimension vector based on text word hashes.
        Enables offline cosine-similarity search for testing and dev.
        """
        vector = [0.0] * dimension
        words = text.lower().split()
        if not words:
            vector[0] = 1.0
            return vector
            
        for word in words:
            # Hash each word and map it to multiple dimensions deterministically
            h = hashlib.md5(word.encode("utf-8")).hexdigest()
            for i in range(4):
                chunk = h[i*8:(i+1)*8]
                val = int(chunk, 16)
                idx = val % dimension
                # Add fractional value based on hash
                vector[idx] += (val / 0xFFFFFFFF) + 0.1

        # Normalize the vector
        norm = sum(x*x for x in vector) ** 0.5
        if norm:
            vector = [x / norm for x in vector]
        else:
            vector[0] = 1.0
        return vector

    async def embed_text(self, text: str) -> list[float]:
        """
        Computes text embedding. Tries Google's SDK or falls back to local hash embeddings.
        """
        if not text:
            return [0.0] * 768

        if self.api_key:
            try:
                import google.generativeai as genai
                # Configure generative AI if not already done
                genai.configure(api_key=self.api_key)
                
                # Fetch embedding using models/embedding-001 (768 dimensions)
                response = genai.embed_content(
                    model="models/embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                emb = response.get("embedding")
                if emb:
                    return list(emb)
            except Exception as e:
                logger.warning(f"Google embedding API call failed: {str(e)}. Falling back to local hashing.")

        # Fallback to local mock embedding
        return self._get_mock_embedding(text)
