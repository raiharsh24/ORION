from typing import Dict, List
from app.capabilities.capability import BaseCapability

class CapabilityRegistry:
    """
    Registry for loading and querying runtime capability modules.

    TODO:
    - Register and unregister capability modules
    - Instantiate capabilities dynamically
    - Query registered capability descriptions and schemas
    """
    def __init__(self) -> None:
        self._capabilities: Dict[str, BaseCapability] = {}

    def register(self, capability: BaseCapability) -> None:
        """
        Registers a capability module.

        Args:
            capability (BaseCapability): Capability instance.
        """
        # TODO: Handle name collisions and logging
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> BaseCapability | None:
        """
        Retrieves a capability by name.

        Args:
            name (str): Capability identifier.

        Returns:
            Optional[BaseCapability]: capability instance or None.
        """
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[BaseCapability]:
        """
        Lists all registered capabilities.

        Returns:
            List[BaseCapability]: List of instances.
        """
        return list(self._capabilities.values())
