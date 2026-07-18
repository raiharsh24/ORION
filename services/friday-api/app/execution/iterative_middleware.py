from typing import Any, Dict, List, Optional
from loguru import logger

from app.execution.context import ExecutionContext
from app.execution.middleware import ExecutionMiddleware
from app.tool_selection.base import ToolSelectionContext
from app.tool_selection.selector import ToolSelectionEngine
from app.tool_execution.executor import ToolExecutionEngine
from app.tool_execution.base import ExecutionMode
from app.tools.base import PermissionLevel


class IterativeExecutionMiddleware(ExecutionMiddleware):
    """Intercepts the EXECUTION stage to run plan steps iteratively.

    For each step in the plan:
    1. Selects the best tool via ToolSelectionEngine (by capability)
    2. Adapts step args to tool input schema
    3. Executes via ToolExecutionEngine
    4. Makes output available for subsequent steps via variable interpolation

    Accumulates all outputs into ctx.tool_output for LLM consumption.
    Sets ctx.metadata["_iterative_done"] = True so the engine skips its
    default execution path.
    """

    _ACTION_TO_CAPABILITY: Dict[str, List[str]] = {
        "filesystem_op": ["filesystem"],
        "terminal_exec": ["terminal"],
        "memory_op": ["memory"],
        "web_search": ["browser", "web"],
        "process_prompt": ["llm"],
    }

    def __init__(
        self,
        tool_selection_engine: ToolSelectionEngine,
        tool_execution_engine: ToolExecutionEngine,
        max_iterations: int = 10,
    ) -> None:
        self._selection_engine = tool_selection_engine
        self._execution_engine = tool_execution_engine
        self._max_iterations = max_iterations

    async def before_execution(self, ctx: ExecutionContext) -> None:
        plan = ctx.plan
        if not plan:
            return

        steps = getattr(plan, "steps", None)
        if not steps:
            return

        logger.info(
            f"IterativeExecutionMiddleware executing {len(steps)} step(s)"
        )

        accumulated_output = ""
        iteration_results: List[Dict[str, Any]] = []
        step_outputs: Dict[str, str] = {}

        for idx, step in enumerate(steps):
            if idx >= self._max_iterations:
                logger.warning(f"Reached max iterations ({self._max_iterations})")
                break

            if ctx.cancelled:
                break

            step_result = await self._execute_step(
                ctx, step, idx, step_outputs,
            )
            iteration_results.append(step_result)

            if step_result.get("output"):
                action = step.get("action", f"step_{idx}")
                step_outputs[action] = step_result["output"]
                step_outputs[str(idx)] = step_result["output"]

                accumulated_output += (
                    f"--- Step {idx + 1}: {action} ---\n"
                    f"{step_result['output']}\n\n"
                )

            if not step_result.get("success") and not step.get("optional"):
                logger.warning(
                    f"Step {idx + 1} failed and is not optional, halting"
                )
                break

        ctx.tool_output = accumulated_output.strip()
        ctx.metadata["iterative_results"] = iteration_results
        ctx.metadata["_iterative_done"] = True

    async def _execute_step(
        self,
        ctx: ExecutionContext,
        step: Dict[str, Any],
        step_idx: int,
        previous_outputs: Dict[str, str],
    ) -> Dict[str, Any]:
        action = step.get("action", "unknown")
        step_args = dict(step.get("args", {}))

        step_args = self._interpolate_args(step_args, previous_outputs)

        capabilities = self._resolve_capabilities(action, step_args)
        selection = await self._selection_engine.select(
            ToolSelectionContext(
                required_capabilities=capabilities,
                required_categories=["filesystem"],
                user_permission_level=PermissionLevel.USER,
            )
        )

        generic_caps = {"filesystem", "terminal", "browser", "memory", "web", "llm", "desktop"}
        specific_caps = [c for c in capabilities if c not in generic_caps]
        if specific_caps:
            selection.selected_tools = [
                st for st in selection.selected_tools
                if any(cap in st.tool.name.lower() or cap in st.tool.description.lower()
                       for cap in specific_caps)
            ]

        if not selection.selected_tools:
            return {
                "step": step_idx,
                "action": action,
                "success": False,
                "error": f"No tool found for capabilities: {capabilities}",
                "output": "",
            }

        args_overrides: Dict[str, Dict[str, Any]] = {}
        for st in selection.selected_tools:
            tool_id = st.tool.id
            adapted = self._adapt_args(st.tool.name, step_args)
            args_overrides[tool_id] = adapted

        exec_result = await self._execution_engine.execute(
            selection_result=selection,
            args_overrides=args_overrides,
            mode=ExecutionMode.SEQUENTIAL,
            cancellation_token=ctx.cancellation_token,
        )

        outputs = []
        all_success = True
        errors = []

        for r in exec_result.results:
            if r.success:
                outputs.append(str(r.output))
            else:
                all_success = False
                errors.append(f"{r.tool_id}: {r.error or 'Unknown error'}")

        return {
            "step": step_idx,
            "action": action,
            "tool_ids": selection.tool_ids,
            "success": all_success,
            "output": "\n".join(outputs) if outputs else "",
            "error": "; ".join(errors) if errors else None,
        }

    def _resolve_capabilities(
        self,
        action: str,
        args: Dict[str, Any],
    ) -> List[str]:
        op = args.get("op", "")
        if op:
            op_cap_map = {
                "read": ["read_file"],
                "write": ["write_file"],
                "list": ["list_directory"],
                "delete": ["delete_file"],
                "search": ["search_files"],
                "info": ["file_info"],
            }
            specific = op_cap_map.get(op)
            if specific:
                return specific

        return list(self._ACTION_TO_CAPABILITY.get(action, [action]))

    def _interpolate_args(
        self,
        args: Dict[str, Any],
        previous_outputs: Dict[str, str],
    ) -> Dict[str, Any]:
        result = {}
        for key, value in args.items():
            if isinstance(value, str) and "${" in value:
                for var_name, var_value in previous_outputs.items():
                    placeholder = f"${{{var_name}}}"
                    if placeholder in value:
                        value = value.replace(placeholder, var_value)
            result[key] = value
        return result

    def _adapt_args(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Adapt generic plan step args to tool-specific input schema."""
        adapted = {k: v for k, v in args.items() if v is not None}

        n = tool_name.lower()

        if "search" in n:
            adapted.pop("op", None)
            if "root" not in adapted and "path" in adapted:
                adapted["root"] = adapted.pop("path")

        adapted.pop("op", None)

        return adapted


class IterativeExecutionObserver(ExecutionMiddleware):
    """Non-invasive middleware that observes and logs iterative execution
    results without modifying execution behaviour."""

    async def after_execution(self, ctx: ExecutionContext) -> None:
        results = ctx.metadata.get("iterative_results")
        if results:
            total = len(results)
            succeeded = sum(1 for r in results if r.get("success"))
            logger.info(
                f"Iterative execution complete: {succeeded}/{total} steps succeeded"
            )
