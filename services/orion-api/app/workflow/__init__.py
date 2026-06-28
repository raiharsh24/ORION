"""
Workflow package — ORION Workflow Engine.

Exports all public interfaces for the workflow subsystem.
"""
from app.workflow.workflow import (
    Workflow,
    WorkflowNode,
    WorkflowStatus,
    WorkflowNodeStatus,
    WorkflowNodeType,
    WorkflowFlowType,
    ConditionConfig,
)
from app.workflow.engine import WorkflowEngine
from app.workflow.runner import WorkflowRunner
from app.workflow.executor import WorkflowNodeExecutor
from app.workflow.history import WorkflowHistory, WorkflowRun, WorkflowRunStatus
from app.workflow.templates import WorkflowTemplate, build_workflow_from_template, list_templates
from app.workflow.graph import (
    has_cycle,
    topological_sort,
    propagate_statuses,
    get_runnable_nodes,
    get_parallel_groups,
    get_next_node,
)
from app.workflow.conditions import evaluate_condition
from app.workflow.variables import (
    resolve_variables,
    resolve_template_string,
    set_variable,
    merge_outputs,
)

__all__ = [
    # Models
    "Workflow",
    "WorkflowNode",
    "WorkflowStatus",
    "WorkflowNodeStatus",
    "WorkflowNodeType",
    "WorkflowFlowType",
    "ConditionConfig",
    # Engine
    "WorkflowEngine",
    "WorkflowRunner",
    "WorkflowNodeExecutor",
    # History
    "WorkflowHistory",
    "WorkflowRun",
    "WorkflowRunStatus",
    # Templates
    "WorkflowTemplate",
    "build_workflow_from_template",
    "list_templates",
    # Graph
    "has_cycle",
    "topological_sort",
    "propagate_statuses",
    "get_runnable_nodes",
    "get_parallel_groups",
    "get_next_node",
    # Conditions
    "evaluate_condition",
    # Variables
    "resolve_variables",
    "resolve_template_string",
    "set_variable",
    "merge_outputs",
]
