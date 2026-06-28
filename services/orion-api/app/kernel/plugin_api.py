from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class OrionPlugin(ABC):
    """
    Abstract base class defining the standard extension interface for all ORION plugins.
    Allows independent third-party code to integrate with ORION core lifecycles and event bus.
    """
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Returns plugin metadata dictionary containing:
        - name: str
        - version: str (e.g. '1.0.0')
        - description: str
        - author: str
        - target_compatibility: str (e.g. '>=0.4.0')
        """
        pass

    @abstractmethod
    def get_permissions(self) -> List[str]:
        """
        Returns list of permissions/scopes requested by the plugin:
        - e.g. ['filesystem.write', 'terminal.execute']
        """
        pass

    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """
        Returns a list of module or plugin name dependencies.
        """
        pass

    @abstractmethod
    def get_events(self) -> List[str]:
        """
        Returns a list of event topic patterns to automatically subscribe to.
        """
        pass

    @abstractmethod
    async def initialize(self, kernel: Any) -> None:
        """
        Invoked by the Lifecycle Manager during initial subsystem load.
        Enables registration of local services and settings hook.
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        Invoked by the Lifecycle Manager during kernel boot ready.
        Enables startup of background loops or websocket feeds.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Invoked by the Lifecycle Manager during graceful kernel shutdown.
        Enables file handle release and context cleanup.
        """
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        """
        Invoked when system configuration values undergo validation changes.
        """
        pass
