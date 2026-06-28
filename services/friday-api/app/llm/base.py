from abc import ABC, abstractmethod
from typing import AsyncGenerator

class BaseLLM(ABC):
    """
    Abstract Base Class defining the standard interface for LLM client adapters in FRIDAY.
    """
    
    @abstractmethod
    async def generate(self, prompt: str, context: str | None = None) -> str:
        """
        Generate a text response based on the provided prompt and context.
        
        Args:
            prompt: The primary query or instruction.
            context: Any context, history, or system details.
            
        Returns:
            The generated response string.
        """
        pass

    @abstractmethod
    async def generate_stream(self, prompt: str, context: str | None = None) -> AsyncGenerator[str, None]:
        """
        Generate a streamed text response (SSE-compatible chunks) based on the prompt and context.
        
        Args:
            prompt: The primary query or instruction.
            context: Any context, history, or system details.
            
        Yields:
            Text chunks of the response as they are generated.
        """
        pass
