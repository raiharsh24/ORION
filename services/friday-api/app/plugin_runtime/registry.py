from typing import Dict, List, Optional, Any
from loguru import logger

from app.plugin_runtime.base import PluginInstance, PluginRuntimeState
from app.plugin_runtime.loader import RuntimePluginLoader


class PluginRuntimeRegistry:
    def __init__(self, loader: RuntimePluginLoader) -> None:
        self._loader = loader

    @property
    def instances(self) -> Dict[str, PluginInstance]:
        return self._loader.instances

    def get(self, plugin_id: str) -> Optional[PluginInstance]:
        return self._loader.get_instance(plugin_id)

    def list_plugins(self) -> List[PluginInstance]:
        return list(self._loader.instances.values())

    def list_by_state(self, state: PluginRuntimeState) -> List[PluginInstance]:
        return [i for i in self._loader.instances.values()
                if i.state == state]

    def list_running(self) -> List[PluginInstance]:
        return [i for i in self._loader.instances.values()
                if i.is_running]

    def list_failed(self) -> List[PluginInstance]:
        return [i for i in self._loader.instances.values()
                if i.state == PluginRuntimeState.FAILED]

    def search(self, query: str) -> List[PluginInstance]:
        q = query.lower()
        return [i for i in self._loader.instances.values()
                if q in i.plugin_id.lower()
                or q in i.name.lower()
                or q in str(i.metadata.get("description", "")).lower()]

    def get_dependents(self, plugin_id: str) -> List[str]:
        dependents = []
        for inst in self._loader.instances.values():
            if plugin_id in inst.dependencies:
                dependents.append(inst.plugin_id)
        return dependents

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        graph = {}
        for inst in self._loader.instances.values():
            graph[inst.plugin_id] = list(inst.dependencies)
        return graph

    def check_dependency_chain(self, plugin_id: str) -> bool:
        visited = set()
        stack = [plugin_id]
        while stack:
            current = stack.pop()
            if current in visited:
                return False
            visited.add(current)
            inst = self._loader.get_instance(current)
            if inst:
                stack.extend(inst.dependencies)
        return True

    def count(self) -> int:
        return len(self._loader.instances)

    def get_plugin_ids(self) -> List[str]:
        return list(self._loader.instances.keys())
