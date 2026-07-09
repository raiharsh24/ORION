from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from app.plugin_sdk.plugin_context import PluginContext


class BasePlugin(ABC):
    id: str = ""
    name: str = ""
    version: str = "1.0.0"

    def __init__(self) -> None:
        self.context: Optional[PluginContext] = None

    def set_context(self, ctx: PluginContext) -> None:
        self.context = ctx

    # ── Lifecycle hooks ──────────────────────────────────────────────────

    async def on_install(self) -> None:
        pass

    async def on_load(self) -> None:
        pass

    async def on_init(self) -> None:
        pass

    async def on_enable(self) -> None:
        pass

    async def on_disable(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    async def on_config_change(self, config: Dict[str, Any]) -> None:
        pass

    # ── Required overrides ───────────────────────────────────────────────

    @abstractmethod
    def get_manifest(self) -> Dict[str, Any]:
        pass

    # ── Permissions ──────────────────────────────────────────────────────

    def get_requested_permissions(self) -> List[str]:
        return []

    # ── Tools ────────────────────────────────────────────────────────────

    def get_tools(self) -> List[Any]:
        return []

    # ── Helpers ──────────────────────────────────────────────────────────

    def log_debug(self, msg: str) -> None:
        if self.context:
            self.context.log_debug(msg)

    def log_info(self, msg: str) -> None:
        if self.context:
            self.context.log_info(msg)

    def log_warning(self, msg: str) -> None:
        if self.context:
            self.context.log_warning(msg)

    def log_error(self, msg: str) -> None:
        if self.context:
            self.context.log_error(msg)
