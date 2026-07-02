from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseCapability(ABC):
    """
    Abstract base for all modular skill/capability implementations.
    """

    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, **kwargs: Any) -> bool:
        raise NotImplementedError
