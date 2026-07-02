from typing import Dict, List, Set, Tuple

from app.tool_execution.base import ExecutionMode, ExecutionContext


class ExecutionScheduler:
    @staticmethod
    def order_tools(
        contexts: List[ExecutionContext],
        mode: ExecutionMode,
        dependency_map: Dict[str, List[str]],
    ) -> List[List[ExecutionContext]]:
        if mode == ExecutionMode.PARALLEL:
            return [contexts]

        if mode == ExecutionMode.DEPENDENCY_AWARE:
            return ExecutionScheduler._topological_layers(contexts, dependency_map)

        return [[ctx] for ctx in contexts]

    @staticmethod
    def _topological_layers(
        contexts: List[ExecutionContext],
        dependency_map: Dict[str, List[str]],
    ) -> List[List[ExecutionContext]]:
        ctx_by_id = {ctx.tool_id: ctx for ctx in contexts}
        all_ids = set(ctx_by_id.keys())

        available = set(all_ids)
        for deps in dependency_map.values():
            available -= set(deps)

        layers: List[List[ExecutionContext]] = []
        remaining = set(all_ids)
        resolved: Set[str] = set()

        while remaining:
            layer_ids = {
                tid for tid in remaining
                if all(d in resolved for d in dependency_map.get(tid, []))
            }
            if not layer_ids:
                remaining_ids = sorted(remaining, key=lambda x: (
                    -len(dependency_map.get(x, [])),
                    x,
                ))
                layer_ids = {remaining_ids[0]}

            layer = sorted(
                [ctx_by_id[tid] for tid in layer_ids],
                key=lambda c: c.priority,
                reverse=True,
            )
            layers.append(layer)
            resolved |= layer_ids
            remaining -= layer_ids

        return layers
