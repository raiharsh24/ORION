from typing import Dict, List, Optional, Set, Tuple
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, PackageDependency, DependencyNode,
    DependencyGraph, DependencyResolution, PackageStatus,
)
from app.plugin_marketplace.events import DependencyResolved
from app.plugins.base import PluginVersion


class DependencyResolver:
    def __init__(self, event_bus=None) -> None:
        self._event_bus = event_bus

    def resolve(self, root_id: str,
                packages: Dict[str, PluginPackage],
                installed: Optional[Dict[str, str]] = None) -> DependencyResolution:
        result = DependencyResolution()
        graph = self._build_graph(packages)

        self._detect_circular(graph, result)
        if result.circular_dependencies:
            result.success = False
            result.messages.append(f"Circular dependencies detected: {result.circular_dependencies}")
            self._publish(root_id, [], False)
            return result

        resolved_order = []
        visited = set()
        in_progress = set()

        def visit(node_id: str) -> bool:
            if node_id in visited:
                return True
            if node_id in in_progress:
                result.circular_dependencies.append([node_id])
                return False
            if node_id not in graph.nodes:
                result.missing_dependencies.append(node_id)
                return False

            in_progress.add(node_id)
            node = graph.nodes[node_id]
            for dep_id in node.dependencies:
                if not visit(dep_id):
                    return False
            in_progress.remove(node_id)
            visited.add(node_id)
            if node_id not in resolved_order:
                resolved_order.append(node_id)
            return True

        if not visit(root_id):
            result.success = False
            result.messages.append("Dependency resolution failed")
            self._publish(root_id, [], False)
            return result

        self._check_version_conflicts(graph, packages, installed, result)
        self._check_missing(graph, packages, result)

        result.success = (not result.missing_dependencies
                          and not result.version_conflicts)
        result.order = resolved_order
        if result.success:
            result.messages.append(f"Resolved {len(resolved_order)} dependencies")
        self._publish(root_id, resolved_order, result.success)
        return result

    def resolve_batch(self, plugin_ids: List[str],
                       packages: Dict[str, PluginPackage]) -> DependencyResolution:
        result = DependencyResolution()
        all_order = []
        all_circular = []
        all_missing = []
        all_conflicts = []

        for pid in plugin_ids:
            sub = self.resolve(pid, packages)
            for item in sub.order:
                if item not in all_order:
                    all_order.append(item)
            all_circular.extend(sub.circular_dependencies)
            all_missing.extend(sub.missing_dependencies)
            all_conflicts.extend(sub.version_conflicts)

        result.order = all_order
        result.circular_dependencies = all_circular
        result.missing_dependencies = list(set(all_missing))
        result.version_conflicts = list(set(all_conflicts))
        result.success = (not all_circular and not all_missing
                          and not all_conflicts)
        return result

    def check_circular(self, packages: Dict[str, PluginPackage]) -> List[List[str]]:
        graph = self._build_graph(packages)
        result = DependencyResolution()
        self._detect_circular(graph, result)
        return result.circular_dependencies

    def get_dependency_order(self, packages: Dict[str, PluginPackage]) -> List[str]:
        graph = self._build_graph(packages)
        visited = set()
        order = []

        def visit(node_id: str) -> None:
            if node_id in visited or node_id not in graph.nodes:
                return
            visited.add(node_id)
            node = graph.nodes[node_id]
            for dep_id in node.dependencies:
                visit(dep_id)
            order.append(node_id)

        for pid in list(graph.nodes.keys()):
            visit(pid)
        return order

    def _build_graph(self, packages: Dict[str, PluginPackage]) -> DependencyGraph:
        graph = DependencyGraph()
        for pid, pkg in packages.items():
            node = DependencyNode(
                plugin_id=pid,
                version=pkg.version,
                dependencies=[d.plugin_id for d in pkg.dependencies
                              if not d.optional],
                optional_dependencies=[d.plugin_id for d in pkg.dependencies
                                        if d.optional],
            )
            graph.nodes[pid] = node
        for pid, node in graph.nodes.items():
            for dep_id in node.dependencies:
                if dep_id in graph.nodes:
                    graph.nodes[dep_id].dependents.append(pid)
        return graph

    def _detect_circular(self, graph: DependencyGraph,
                          result: DependencyResolution) -> None:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {pid: WHITE for pid in graph.nodes}
        parent = {}
        cycles = []

        def dfs(node_id: str, path: List[str]) -> None:
            color[node_id] = GRAY
            path.append(node_id)
            node = graph.nodes.get(node_id)
            if node:
                for dep_id in node.dependencies:
                    if dep_id not in graph.nodes:
                        continue
                    if color.get(dep_id) == GRAY:
                        cycle_start = path.index(dep_id)
                        cycles.append(path[cycle_start:] + [dep_id])
                    elif color.get(dep_id) == WHITE:
                        parent[dep_id] = node_id
                        dfs(dep_id, path)
            path.pop()
            color[node_id] = BLACK

        for pid in list(graph.nodes.keys()):
            if color.get(pid) == WHITE:
                dfs(pid, [])

        result.circular_dependencies = cycles

    def _check_version_conflicts(self, graph: DependencyGraph,
                                   packages: Dict[str, PluginPackage],
                                   installed: Optional[Dict[str, str]],
                                   result: DependencyResolution) -> None:
        required_versions = {}
        for pid, node in graph.nodes.items():
            pkg = packages.get(pid)
            if pkg:
                if pid in required_versions:
                    if pkg.version != required_versions[pid]:
                        result.version_conflicts.append(
                            f"{pid}: {required_versions[pid]} vs {pkg.version}"
                        )
                else:
                    required_versions[pid] = pkg.version

    def _check_missing(self, graph: DependencyGraph,
                        packages: Dict[str, PluginPackage],
                        result: DependencyResolution) -> None:
        all_refs = set()
        for node in graph.nodes.values():
            all_refs.update(node.dependencies)
        for ref in all_refs:
            if ref not in packages:
                result.missing_dependencies.append(ref)
            elif packages[ref].status == PackageStatus.BROKEN:
                result.missing_dependencies.append(f"{ref} (broken)")

    def _publish(self, plugin_id: str, deps: List[str],
                  success: bool) -> None:
        if self._event_bus:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(self._event_bus.publish(
                            DependencyResolved(
                                plugin_id=plugin_id,
                                dependencies=deps,
                                success=success,
                            )
                        ))
                except RuntimeError:
                    pass
            except Exception:
                pass
