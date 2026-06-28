from typing import Dict, List, Any, Callable, Optional
from loguru import logger

class OrionModuleMetadata:
    """
    Metadata representation for a registered system module.
    """
    def __init__(self, name: str, version: str, dependencies: List[str]) -> None:
        self.name = name
        self.version = version
        self.dependencies = dependencies
        self.status = "registered"

class OrionModuleRegistry:
    """
    Registry managing runtime modules, metadata, and dependency order.
    """
    def __init__(self) -> None:
        self._modules: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._metadata: Dict[str, OrionModuleMetadata] = {}

    def register_module(
        self,
        name: str,
        version: str,
        dependencies: Optional[List[str]] = None,
        instance_or_factory: Any = None,
        lazy: bool = False
    ) -> None:
        """Registers a subsystem module and its dependencies."""
        deps = dependencies or []
        meta = OrionModuleMetadata(name, version, deps)
        self._metadata[name] = meta

        if lazy and callable(instance_or_factory):
            logger.info(f"Registering lazy module: '{name}' v{version} (dependencies: {deps})")
            self._factories[name] = instance_or_factory
            if name in self._modules:
                del self._modules[name]
        else:
            logger.info(f"Registering module: '{name}' v{version} (dependencies: {deps})")
            self._modules[name] = instance_or_factory
            if name in self._factories:
                del self._factories[name]

    def unregister_module(self, name: str) -> None:
        """Removes a module from the registry."""
        logger.info(f"Unregistering module: '{name}'")
        self._modules.pop(name, None)
        self._factories.pop(name, None)
        self._metadata.pop(name, None)

    def get_module(self, name: str) -> Optional[Any]:
        """Resolves a module, instantiating it lazily if necessary."""
        if name in self._modules:
            return self._modules[name]
        if name in self._factories:
            logger.debug(f"Initializing lazy module: '{name}'")
            try:
                instance = self._factories[name]()
                self._modules[name] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to resolve lazy module '{name}': {str(e)}")
                raise e
        return None

    def get_metadata(self, name: str) -> Optional[OrionModuleMetadata]:
        """Retrieves module metadata."""
        return self._metadata.get(name)

    def list_modules(self) -> List[str]:
        """Lists all registered modules."""
        return list(set(self._modules.keys()) | set(self._factories.keys()))

    def topological_sort(self) -> List[str]:
        """
        Sorts modules topologically by their dependencies.
        Raises ValueError if a cyclic dependency path is detected.
        """
        visited: Dict[str, str] = {}
        order: List[str] = []

        def visit(node: str):
            state = visited.get(node)
            if state == "visiting":
                raise ValueError(f"Cyclic dependency detected involving module '{node}'")
            if state == "visited":
                return

            visited[node] = "visiting"
            meta = self._metadata.get(node)
            if meta:
                for dep in meta.dependencies:
                    # Only traverse registered dependencies
                    if dep in self._metadata:
                        visit(dep)
            visited[node] = "visited"
            order.append(node)

        for name in list(self._metadata.keys()):
            if name not in visited:
                visit(name)

        return order
