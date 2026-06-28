from typing import Dict, List, Any, Optional, Callable
from loguru import logger

class OrionServiceRegistry:
    """
    Service registry class acts as the centralized locator of system components.
    Supports dependency injection and lazy service lookup.
    """
    def __init__(self) -> None:
        """Initialize the OrionServiceRegistry."""
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}

    def register(self, name: str, service: Any, lazy: bool = False) -> None:
        """
        Registers a service instance or factory.

        Args:
            name (str): Unique name identifier.
            service (Any): Service instance or factory callable.
            lazy (bool): If True and service is callable, it will be initialized on first get.
        """
        logger.info(f"Registering service: '{name}' (lazy={lazy})")
        if lazy and callable(service):
            self._factories[name] = service
            if name in self._services:
                del self._services[name]
        else:
            self._services[name] = service
            if name in self._factories:
                del self._factories[name]

    def unregister(self, name: str) -> None:
        """
        Deregisters a service by name.

        Args:
            name (str): Unique name identifier.
        """
        logger.info(f"Unregistering service: '{name}'")
        if name in self._services:
            del self._services[name]
        if name in self._factories:
            del self._factories[name]

    def get(self, name: str) -> Optional[Any]:
        """
        Retrieves a service dependency by name. Resolves lazy factories if needed.

        Args:
            name (str): Unique name identifier.

        Returns:
            Optional[Any]: Registered service instance or None.
        """
        if name in self._services:
            return self._services[name]
        
        if name in self._factories:
            logger.debug(f"Initializing lazy service: '{name}'")
            factory = self._factories[name]
            try:
                instance = factory()
                self._services[name] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to initialize lazy service '{name}': {str(e)}")
                raise e
                
        return None

    def exists(self, name: str) -> bool:
        """
        Checks if a service registry entry exists.

        Args:
            name (str): Unique name identifier.

        Returns:
            bool: True if service or factory is registered.
        """
        return name in self._services or name in self._factories

    def list(self) -> List[str]:
        """
        Lists all registered service identifiers (alias for list_services).

        Returns:
            List[str]: List of service names.
        """
        return self.list_services()

    def list_services(self) -> List[str]:
        """
        Lists all registered service identifiers.

        Returns:
            List[str]: List of service names.
        """
        return list(set(self._services.keys()) | set(self._factories.keys()))
