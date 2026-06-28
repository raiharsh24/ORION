from loguru import logger

class AIService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        logger.info("AI Service initialized as a stub provider.")

    async def generate_response(self, prompt: str) -> str:
        logger.debug(f"Generating stub response for query prompt: '{prompt}'")
        # Echo the prompt back as requested for Version 0.2
        return f"Echo: {prompt}"
