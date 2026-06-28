import uuid
from typing import Dict, Any
from app.orion.planner_schema import ExecutionPlan
from app.workflow_runtime.models import ExecutionPlanInput


def execution_plan_to_input(plan: ExecutionPlan) -> ExecutionPlanInput:
    return ExecutionPlanInput(
        plan_id=str(uuid.uuid4()),
        goal=plan.goal,
        steps=plan.steps,
        variables={
            "intent": plan.intent,
            "priority": plan.priority,
            "confidence": plan.confidence,
        },
        metadata={
            "capabilities": plan.capabilities,
            "memory_required": plan.memoryRequired,
            "tool_required": plan.toolRequired,
            "clarification_required": plan.clarificationRequired,
            "tool_name": plan.tool_name,
            "reasoning": plan.reasoning,
        },
    )


def extract_tool_output(workflow: Any) -> Dict[str, Any]:
    tool_outputs = {}
    for step_id, step in workflow.steps.items():
        if step.status.value == "COMPLETED" and step.result:
            tool_outputs[step_id] = step.result
    return tool_outputs


def format_tool_output_for_prompt(tool_outputs: Dict[str, Any]) -> str:
    if not tool_outputs:
        return ""
    parts = []
    for step_id, result in tool_outputs.items():
        if isinstance(result, dict):
            output = result.get("output", result.get("response", str(result)))
        else:
            output = str(result)
        parts.append(f"[{step_id}]: {output}")
    return "\n".join(parts)
