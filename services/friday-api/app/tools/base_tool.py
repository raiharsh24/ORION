from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    """
    Abstract Base Class for all system tools in FRIDAY.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the tool's purpose and parameter schema."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool operation."""
        pass

    def requires_confirmation(self, **kwargs) -> bool:
        """Determine if the specific call with kwargs requires user confirmation."""
        return False
