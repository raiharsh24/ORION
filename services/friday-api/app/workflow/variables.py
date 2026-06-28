"""
Workflow variable resolution and mutation helpers.

Provides:
- Template string interpolation with {{ variables.x }} and {{ nodes.y.outputs.z }}
- Runtime variable mutation for writing node outputs back
- Recursive resolution for nested dicts/lists
"""
import re
from typing import Any, Dict, Optional
from app.workflow.workflow import Workflow, WorkflowNode


# ---------------------------------------------------------------------------
# Internal expression evaluator
# ---------------------------------------------------------------------------

def _evaluate_expression(expr: str, variables: Dict[str, Any], nodes: Dict[str, WorkflowNode]) -> Any:
    """
    Evaluates expression keys such as 'variables.var_name' or
    'nodes.node_id.outputs.result'.
    """
    if expr.startswith("variables."):
        key = expr[len("variables."):]
        return variables.get(key)

    elif expr.startswith("nodes."):
        parts = expr.split(".")
        if len(parts) >= 3:
            node_id = parts[1]
            prop = parts[2]
            node = nodes.get(node_id)
            if not node:
                return None
            if prop == "status":
                return node.status.value if hasattr(node.status, "value") else str(node.status)
            elif prop == "outputs" and len(parts) >= 4:
                out_key = ".".join(parts[3:])
                return node.outputs.get(out_key)
            elif prop == "error":
                return node.error

    return None


# ---------------------------------------------------------------------------
# Template string resolution
# ---------------------------------------------------------------------------

def resolve_template_string(template: str, variables: Dict[str, Any], nodes: Dict[str, WorkflowNode]) -> Any:
    """
    Resolves double curly-braces {{ }} templates inside strings.
    If the template is the entire string, it returns the raw object value.
    """
    pattern = r'\{\{\s*(.*?)\s*\}\}'

    # Exact full match (returns the raw type: bool, int, dict, etc.)
    match = re.fullmatch(pattern, template)
    if match:
        expr = match.group(1).strip()
        return _evaluate_expression(expr, variables, nodes)

    # Substring replacement (returns interpolated string)
    def replacer(m: re.Match) -> str:
        expr = m.group(1).strip()
        val = _evaluate_expression(expr, variables, nodes)
        return str(val) if val is not None else ""

    return re.sub(pattern, replacer, template)


def resolve_variables(value: Any, variables: Dict[str, Any], nodes: Dict[str, WorkflowNode]) -> Any:
    """
    Recursively scans and interpolates any nested string values.
    """
    if isinstance(value, str):
        return resolve_template_string(value, variables, nodes)
    elif isinstance(value, dict):
        return {k: resolve_variables(v, variables, nodes) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_variables(item, variables, nodes) for item in value]
    return value


# ---------------------------------------------------------------------------
# Runtime variable mutation
# ---------------------------------------------------------------------------

def set_variable(workflow: Workflow, key: str, value: Any) -> None:
    """
    Writes a value into the workflow's runtime variables namespace.

    Args:
        workflow: The live Workflow instance.
        key:      Variable name (supports dot-notation prefix strip).
        value:    Any serialisable Python value.
    """
    # Strip leading 'variables.' prefix if caller includes it
    if key.startswith("variables."):
        key = key[len("variables."):]
    workflow.variables[key] = value


def merge_outputs(workflow: Workflow, node: WorkflowNode, outputs: Dict[str, Any]) -> None:
    """
    Merges node execution outputs into:
    1. The node's own outputs dict.
    2. The workflow variables namespace under the key '<node_id>.<output_key>'.

    This allows downstream nodes to reference outputs via
    {{ nodes.<node_id>.outputs.<key> }} or {{ variables.<node_id>.<key> }}.

    Args:
        workflow: Active workflow instance.
        node:     The node that just finished executing.
        outputs:  Key-value output map from the node executor.
    """
    node.outputs.update(outputs)

    # Expose under variables namespace for convenience
    for k, v in outputs.items():
        workflow.variables[f"{node.id}.{k}"] = v
