import google.generativeai as genai
from app.llm.base import BaseLLM
from loguru import logger
from typing import AsyncGenerator
import time

class GeminiAdapter(BaseLLM):
    """
    Adapter implementation for the official Google Gemini SDK.
    """
    def __init__(
        self, 
        api_key: str | None = None, 
        model_name: str = "gemini-1.5-flash", 
        temperature: float = 0.7, 
        max_tokens: int = 2048, 
        top_p: float = 0.95
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self._initialized = False

        if api_key and api_key.strip():
            try:
                genai.configure(api_key=api_key)
                self._initialized = True
                logger.info(f"Google Gemini SDK configured successfully with model '{model_name}'.")
            except Exception as e:
                logger.error(f"Failed to configure Gemini SDK: {str(e)}")
        else:
            logger.warning("GeminiAdapter initialized without a valid GEMINI_API_KEY.")

    def _get_model(self) -> genai.GenerativeModel:
        if not self.api_key or not self.api_key.strip():
            from app.core.config import settings as core_settings
            self.api_key = core_settings.GEMINI_API_KEY

        if not self.api_key or not self.api_key.strip():
            raise ValueError("GEMINI_API_KEY is missing or empty. Please verify settings.")
        
        if not self._initialized:
            try:
                genai.configure(api_key=self.api_key)
                self._initialized = True
            except Exception as e:
                raise RuntimeError(f"Failed to configure Gemini SDK dynamically: {str(e)}")

        config = genai.types.GenerationConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
            top_p=self.top_p
        )
        return genai.GenerativeModel(self.model_name, generation_config=config)

    async def generate(self, prompt: str, context: str | None = None) -> str:
        logger.debug(f"Gemini generation request: model={self.model_name}")
        full_content = f"{context}\n\n{prompt}" if context else prompt
        
        try:
            model = self._get_model()
            response = await model.generate_content_async(full_content)
            
            if not response or not response.text:
                raise ValueError("Received empty or invalid response content from Gemini API.")
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {type(e).__name__}: {str(e)}")
            raise e

    async def generate_stream(self, prompt: str, context: str | None = None) -> AsyncGenerator[str, None]:
        logger.debug(f"Gemini streaming request: model={self.model_name}")
        full_content = f"{context}\n\n{prompt}" if context else prompt
        
        try:
            model = self._get_model()
            response_stream = await model.generate_content_async(full_content, stream=True)
            async for chunk in response_stream:
                if chunk and chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini streaming failed: {type(e).__name__}: {str(e)}")
            raise e
