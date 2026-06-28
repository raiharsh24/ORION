from typing import Dict, List, Any, Optional
from loguru import logger

class OrionCapabilityInfo:
    """
    Representation of a capability registered by a module.
    """
    def __init__(self, name: str, module_name: str, description: str, schema: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.module_name = module_name
        self.description = description
        self.schema = schema or {}

class OrionCapabilityRegistry:
    """
    Registry for capability discovery. Decouples system capability lookups from their
    concrete implementing modules.
    """
    def __init__(self) -> None:
        self._capabilities: Dict[str, OrionCapabilityInfo] = {}

    def register_capability(self, name: str, module_name: str, description: str, schema: Optional[Dict[str, Any]] = None) -> None:
        """Registers a system capability."""
        logger.info(f"Registering capability '{name}' implemented by module '{module_name}'")
        self._capabilities[name] = OrionCapabilityInfo(name, module_name, description, schema)

    def unregister_capability(self, name: str) -> None:
        """Removes a capability registration."""
        logger.info(f"Unregistering capability: '{name}'")
        self._capabilities.pop(name, None)

    def get_capability(self, name: str) -> Optional[OrionCapabilityInfo]:
        """Resolves capability metadata by name."""
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[str]:
        """Lists all registered capability names."""
        return list(self._capabilities.keys())

    def discover_capabilities(self) -> List[Dict[str, Any]]:
        """
        Returns a serializable catalog of all registered capabilities.
        Used by the Planner or Gateway to check system feature offerings.
        """
        return [
            {
                "name": cap.name,
                "module_name": cap.module_name,
                "description": cap.description,
                "schema": cap.schema
            }
            for cap in self._capabilities.values()
        ]
