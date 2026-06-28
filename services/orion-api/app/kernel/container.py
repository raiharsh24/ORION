from typing import Dict, Any, Callable, List, Optional
from loguru import logger

class OrionServiceContainer:
    """
    Dependency Injection Container resolving dependencies with singleton, 
    transient, or parameterized factory scoping.
    """
    def __init__(self) -> None:
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._scopes: Dict[str, str] = {}
        self._raw_callables: Dict[str, Callable[..., Any]] = {}

    def register_singleton(self, name: str, item: Any) -> None:
        """Registers a singleton service. Always returns the same instance."""
        logger.debug(f"Registering singleton service: '{name}'")
        self._scopes[name] = "singleton"
        if callable(item):
            self._factories[name] = item
            if name in self._singletons:
                del self._singletons[name]
        else:
            self._singletons[name] = item
            if name in self._factories:
                del self._factories[name]

    def register(self, name: str, service: Any, lazy: bool = False) -> None:
        """Backward compatible register method mapping to singleton registration."""
        self._scopes[name] = "singleton"
        if lazy and callable(service):
            self._factories[name] = service
            if name in self._singletons:
                del self._singletons[name]
        else:
            self._singletons[name] = service
            if name in self._factories:
                del self._factories[name]

    def register_transient(self, name: str, factory: Callable[[], Any]) -> None:
        """Registers a transient service. Instantiated anew on every get() call."""
        logger.debug(f"Registering transient service: '{name}'")
        if not callable(factory):
            raise ValueError(f"Transient registration for '{name}' must provide a factory callable.")
        self._scopes[name] = "transient"
        self._factories[name] = factory
        if name in self._singletons:
            del self._singletons[name]

    def register_factory(self, name: str, factory: Callable[..., Any]) -> None:
        """Registers a factory builder. Invoked with parameters during get() requests."""
        logger.debug(f"Registering factory service: '{name}'")
        if not callable(factory):
            raise ValueError(f"Factory registration for '{name}' must provide a factory callable.")
        self._scopes[name] = "factory"
        self._raw_callables[name] = factory
        if name in self._singletons:
            del self._singletons[name]
        if name in self._factories:
            del self._factories[name]

    def get(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Resolves a service from the container.
        
        Args:
            name: Service name identifier.
            args: Positional args passed if scope is 'factory'.
            kwargs: Keyword args passed if scope is 'factory'.
        """
        scope = self._scopes.get(name)
        if not scope:
            raise KeyError(f"Service '{name}' is not registered in the service container.")

        if scope == "singleton":
            if name in self._singletons:
                return self._singletons[name]
            factory = self._factories.get(name)
            if not factory:
                raise KeyError(f"Singleton instance or factory for '{name}' is missing.")
            instance = factory()
            self._singletons[name] = instance
            return instance

        elif scope == "transient":
            factory = self._factories.get(name)
            if not factory:
                raise KeyError(f"Transient factory for '{name}' is missing.")
            return factory()

        elif scope == "factory":
            factory = self._raw_callables.get(name)
            if not factory:
                raise KeyError(f"Factory builder callable for '{name}' is missing.")
            return factory(*args, **kwargs)

        raise ValueError(f"Unknown scope configuration: '{scope}' for service '{name}'.")

    def has(self, name: str) -> bool:
        """Checks if a service registration exists in the container."""
        return name in self._scopes

    def unregister(self, name: str) -> None:
        """Removes a service registration from the container."""
        logger.debug(f"Unregistering service from container: '{name}'")
        self._scopes.pop(name, None)
        self._singletons.pop(name, None)
        self._factories.pop(name, None)
        self._raw_callables.pop(name, None)

    def list_services(self) -> List[str]:
        """Lists all registered service names."""
        return list(self._scopes.keys())
