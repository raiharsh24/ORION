from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseCapability(ABC):
    """
    Abstract Base Class for all automation capability actions.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique name of the capability."""
        pass

    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """Returns the expected argument validation schema."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Set up connection parameters and resources.
        """
        pass

    @abstractmethod
    async def validate(self, **kwargs) -> bool:
        """
        Validates argument values against structural schemas.

        Returns:
            bool: True if input arguments are valid.
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Runs the primary action command.

        Returns:
            Any: Output results from action execution.
        """
        pass

    @abstractmethod
    async def rollback(self) -> bool:
        """
        Undoes action commands to restore previous states.

        Returns:
            bool: True if state restoration succeeded.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Closes connections and cleans up active resources.
        """
        pass
