"""
Workflow condition evaluator.

Evaluates conditions that drive branching decisions in Conditional and Loop
workflow nodes.

Supported condition types:
  - expression:      Generic Python expression with variables/nodes context
  - status_check:    Check a node's current status against an expected value
  - comparison:      Left / right comparison with operator (==, !=, <, >, <=, >=)
  - boolean:         Static true/false constant
  - mission_status:  Live check against MissionManager (via Kernel)
  - desktop_status:  Live check against DesktopAutomationService (via Kernel)
"""
from typing import Any, Dict, Optional
from loguru import logger
from app.workflow.workflow import WorkflowNode


# ---------------------------------------------------------------------------
# Safe expression evaluator
# ---------------------------------------------------------------------------

def _safe_eval(expr: str, context: Dict[str, Any]) -> Any:
    """
    Evaluates a simple Python expression with a restricted built-in environment.
    """
    try:
        safe_globals = {"__builtins__": {}}
        return eval(expr, safe_globals, context)
    except Exception as e:
        logger.error(f"Safe eval failed for expression '{expr}': {str(e)}")
        return False


# ---------------------------------------------------------------------------
# Primary condition evaluator
# ---------------------------------------------------------------------------

def evaluate_condition(
    condition_type: str,
    params: Dict[str, Any],
    variables: Dict[str, Any],
    nodes: Dict[str, WorkflowNode]
) -> bool:
    """
    Evaluates different condition types and returns a boolean result.

    Args:
        condition_type: One of the supported types listed above.
        params:         Condition-specific parameters dict.
        variables:      Current workflow runtime variables.
        nodes:          All WorkflowNode instances keyed by node_id.

    Returns:
        bool: True if condition is met, False otherwise.
    """
    try:
        # ------------------------------------------------------------------
        # 1. Generic Python expression
        # ------------------------------------------------------------------
        if condition_type == "expression":
            expr = params.get("expression", "")
            context = {
                "variables": variables,
                "nodes": {
                    nid: {
                        "status":  node.status.value if hasattr(node.status, "value") else str(node.status),
                        "outputs": node.outputs,
                        "error":   node.error
                    }
                    for nid, node in nodes.items()
                }
            }
            return bool(_safe_eval(expr, context))

        # ------------------------------------------------------------------
        # 2. Node status check
        # ------------------------------------------------------------------
        elif condition_type == "status_check":
            node_id = params.get("node_id")
            expected_status = params.get("status")
            if not node_id:
                logger.warning("status_check condition missing 'node_id'.")
                return False
            node = nodes.get(node_id)
            if not node:
                logger.warning(f"status_check: node '{node_id}' not found.")
                return False
            node_status_str = node.status.value if hasattr(node.status, "value") else str(node.status)
            return node_status_str == expected_status

        # ------------------------------------------------------------------
        # 3. Scalar comparison
        # ------------------------------------------------------------------
        elif condition_type == "comparison":
            from app.workflow.variables import resolve_variables
            left_val  = resolve_variables(params.get("left"),  variables, nodes)
            right_val = resolve_variables(params.get("right"), variables, nodes)
            op = params.get("operator", "==")
            if op == "==":
                return left_val == right_val
            elif op == "!=":
                return left_val != right_val
            elif op == "<":
                return float(left_val) < float(right_val)
            elif op == ">":
                return float(left_val) > float(right_val)
            elif op == "<=":
                return float(left_val) <= float(right_val)
            elif op == ">=":
                return float(left_val) >= float(right_val)
            else:
                logger.warning(f"Unsupported comparison operator: {op}")
                return False

        # ------------------------------------------------------------------
        # 4. Boolean constant
        # ------------------------------------------------------------------
        elif condition_type == "boolean":
            value = params.get("value", False)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)

        # ------------------------------------------------------------------
        # 5. Live Mission Engine status check
        # ------------------------------------------------------------------
        elif condition_type == "mission_status":
            mission_id      = params.get("mission_id")
            expected_status = params.get("status")
            if not mission_id:
                logger.warning("mission_status condition missing 'mission_id'.")
                return False
            try:
                from app.kernel.kernel import OrionKernel
                mission_engine = OrionKernel.get_instance().get_service("mission_engine")
                if not mission_engine:
                    return False
                mission = mission_engine._active_missions.get(mission_id)
                if not mission:
                    return False
                return mission.status.value == expected_status
            except Exception as e:
                logger.error(f"mission_status condition error: {e}")
                return False

        # ------------------------------------------------------------------
        # 6. Live Desktop Automation status check
        # ------------------------------------------------------------------
        elif condition_type == "desktop_status":
            expected_task: Optional[str] = params.get("current_task")
            expect_idle: bool = params.get("expect_idle", False)
            try:
                from app.kernel.kernel import OrionKernel
                desktop_svc = OrionKernel.get_instance().get_service("desktop_automation")
                if not desktop_svc:
                    return False
                diags = desktop_svc.get_diagnostics()
                if expect_idle:
                    return diags.get("current_desktop_task") in (None, "None", "")
                if expected_task:
                    return diags.get("current_desktop_task") == expected_task
                # Default: just check if desktop service is alive
                return True
            except Exception as e:
                logger.error(f"desktop_status condition error: {e}")
                return False

        # ------------------------------------------------------------------
        # Unknown type
        # ------------------------------------------------------------------
        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return False

    except Exception as e:
        logger.error(f"Error evaluating condition '{condition_type}': {str(e)}")
        return False
