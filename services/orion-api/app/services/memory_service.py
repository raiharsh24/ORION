from loguru import logger

class MemoryService:
    def __init__(self) -> None:
        logger.info("Memory Service initialized as a stub provider.")

    async def get_embeddings(self, text: str) -> list[float]:
        logger.debug(f"Generating mock embedding vector for text: '{text[:20]}...'")
        # Return a zeroed out vector representing 1536 embedding dimensions
        return [0.0] * 1536
