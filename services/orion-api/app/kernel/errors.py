from typing import Dict, Any, Optional

class OrionError(Exception):
    """
    Base system exception for all ORION platform errors.
    Supports structured dictionary serialization for secure frontend delivery.
    """
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serializes exception details to a frontend-safe dict structure."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "success": False
        }

class ValidationError(OrionError):
    """Raised when data schemas fail parameter constraints."""
    pass

class ProviderError(OrionError):
    """Raised when external providers (e.g. LLM API, vector store) encounter runtime faults."""
    pass

class MemoryError(OrionError):
    """Raised when context memory buffers fail to read or write."""
    pass

class ToolError(OrionError):
    """Raised during tool parameter parsing or execution failures."""
    pass

class WorkflowError(OrionError):
    """Raised when executing workflow templates or tracking workflow sequences."""
    pass

class KernelError(OrionError):
    """Raised during fatal kernel initialization or boot phases."""
    pass

class ConfigurationError(OrionError):
    """Raised when environment variables or dynamic parameters fail validation checks."""
    pass
