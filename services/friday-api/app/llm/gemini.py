import google.generativeai as genai
from app.llm.base import BaseLLM
from loguru import logger
from typing import AsyncGenerator
import time
import asyncio

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

        self._mock_mode = not api_key or api_key.strip() == "mock" or api_key.strip() == "placeholder" or "your_" in api_key
        self._valid_key = not self._mock_mode
        if self._valid_key:
            try:
                genai.configure(api_key=api_key)
                self._initialized = True
                logger.info(f"Google Gemini SDK configured successfully with model '{model_name}'.")
            except Exception as e:
                logger.error(f"Failed to configure Gemini SDK: {str(e)}")
        else:
            logger.warning("GeminiAdapter initialized in mock mode.")

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

    def _generate_mock(self, prompt: str) -> str:
        p_lower = prompt.lower()
        idx = p_lower.rfind("user prompt:")
        user_msg = p_lower[idx+12:].strip() if idx != -1 else p_lower
        words = set(user_msg.split())
        if ("project" in words or "workspace" in words) and ("scan" in words or "list" in words or "show" in words):
            return "Workspace scan completed. The current active repository is located at `/home/warlock/ORION`. I can see a desktop app and the friday-api backend service."
        if "hello" in words or "hi" in words or "hey" in words:
            return "Hello! I am FRIDAY, your desktop AI operating system. I'm running in development mode. How can I help you today?"
        if "help" in words or user_msg.startswith("what can you"):
            return "I can help with task automation, workspace file operations, knowledge graph navigation, code analysis, system monitoring, and more. I'm currently in development mode so some features use simulated responses."
        if "time" in words or "date" in words or "weather" in words:
            return "I don't have access to real-time data in development mode. Once connected to the Gemini API with a valid key, I can answer questions and retrieve live information."
        return "Hello! I'm FRIDAY, your desktop AI operating system. I received your message. I'm currently in development mode using simulated responses. How can I assist you?"

    async def _generate_mock_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        response = self._generate_mock(prompt)
        words = response.split(" ")
        for i, word in enumerate(words):
            yield (word + " ") if i < len(words) - 1 else word
            await asyncio.sleep(0.03)

    async def generate(self, prompt: str, context: str | None = None) -> str:
        logger.debug(f"Gemini generation request: model={self.model_name}")
        full_content = f"{context}\n\n{prompt}" if context else prompt
        
        # Ensure initialization status matches the latest settings/api_key.
        if not self.api_key or not self.api_key.strip():
            from app.core.config import settings as core_settings
            self.api_key = core_settings.GEMINI_API_KEY

        self._mock_mode = not self.api_key or self.api_key.strip() == "mock" or self.api_key.strip() == "placeholder" or "your_" in self.api_key

        if not self._mock_mode and not self._initialized:
            try:
                genai.configure(api_key=self.api_key)
                self._initialized = True
            except Exception as e:
                logger.error(f"Gemini re-initialization failed in generate(): {e}")

        if self._mock_mode:
            logger.error("Gemini in mock mode during generate() call")
            return self._generate_mock(prompt)

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
        
        self._mock_mode = not self.api_key or self.api_key.strip() == "mock" or self.api_key.strip() == "placeholder" or "your_" in self.api_key

        if not self._mock_mode and not self._initialized:
            try:
                genai.configure(api_key=self.api_key)
                self._initialized = True
            except Exception as e:
                logger.error(f"Gemini re-initialization failed in generate_stream(): {e}")

        if self._mock_mode:
            logger.error("Gemini in mock mode during generate_stream() call")
            async for chunk in self._generate_mock_stream(prompt):
                yield chunk
            return

        try:
            model = self._get_model()
            response_stream = await model.generate_content_async(full_content, stream=True)
            async for chunk in response_stream:
                if chunk and chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini streaming failed: {type(e).__name__}: {str(e)}")
            raise e
