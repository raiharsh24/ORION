from typing import Optional
from app.plugins.base import Plugin


class PluginWrapper:
    def __init__(self, plugin: Plugin) -> None:
        self._plugin = plugin

    @property
    def plugin(self) -> Plugin:
        return self._plugin

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
