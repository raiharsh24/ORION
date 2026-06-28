"""
Built-in Workflow Templates for ORION.

Each template is a fully specified Workflow definition that can be
instantiated via build_workflow_from_template().

Available templates:
  - dev_startup             Development environment initialisation
  - knowledge_sync          Vector DB sync pipeline
  - desktop_automation_demo Desktop automation showcase
  - health_check_pipeline   System health probe sequence
"""
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel

from app.workflow.workflow import (
    Workflow, WorkflowNode, WorkflowNodeType,
    WorkflowFlowType, WorkflowStatus, ConditionConfig
)


# ---------------------------------------------------------------------------
# Template meta model
# ---------------------------------------------------------------------------

class WorkflowTemplate(BaseModel):
    """Metadata describing a built-in workflow template."""
    id: str
    name: str
    description: str
    category: str
    tags: list = []
    flow_type: WorkflowFlowType = WorkflowFlowType.SEQUENTIAL

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

BUILTIN_TEMPLATES: Dict[str, WorkflowTemplate] = {
    "dev_startup": WorkflowTemplate(
        id="dev_startup",
        name="Development Startup",
        description="Initialise dev services, run health checks, and open dev tools.",
        category="development",
        tags=["devops", "startup"],
        flow_type=WorkflowFlowType.SEQUENTIAL,
    ),
    "knowledge_sync": WorkflowTemplate(
        id="knowledge_sync",
        name="Knowledge Sync Pipeline",
        description="Query knowledge base, summarise via LLM, notify on completion.",
        category="knowledge",
        tags=["rag", "knowledge", "llm"],
        flow_type=WorkflowFlowType.SEQUENTIAL,
    ),
    "desktop_automation_demo": WorkflowTemplate(
        id="desktop_automation_demo",
        name="Desktop Automation Demo",
        description="Sequential desktop tasks: notification → folder open → clipboard write → delay → notification.",
        category="automation",
        tags=["desktop", "demo"],
        flow_type=WorkflowFlowType.SEQUENTIAL,
    ),
    "health_check_pipeline": WorkflowTemplate(
        id="health_check_pipeline",
        name="Health Check Pipeline",
        description="Probe API, evaluate health condition, branch to notification or alert.",
        category="system",
        tags=["health", "monitoring"],
        flow_type=WorkflowFlowType.CONDITIONAL,
    ),
}


def list_templates() -> list:
    """Returns all registered built-in template descriptors."""
    return [t.dict() for t in BUILTIN_TEMPLATES.values()]


# ---------------------------------------------------------------------------
# Factory: build_workflow_from_template
# ---------------------------------------------------------------------------

def build_workflow_from_template(
    template_id: str,
    overrides: Optional[Dict[str, Any]] = None
) -> Optional[Workflow]:
    """
    Constructs a ready-to-run Workflow from a built-in template.

    Args:
        template_id: One of the keys in BUILTIN_TEMPLATES.
        overrides:   Optional dict with 'name', 'description', 'variables'.

    Returns:
        A Workflow instance with nodes pre-populated, or None if template not found.
    """
    overrides = overrides or {}
    template = BUILTIN_TEMPLATES.get(template_id)
    if not template:
        return None

    workflow_id = uuid.uuid4().hex
    name        = overrides.get("name", template.name)
    description = overrides.get("description", template.description)
    variables   = overrides.get("variables", {})

    # -----------------------------------------------------------------
    # Template: Development Startup
    # -----------------------------------------------------------------
    if template_id == "dev_startup":
        n_notify = WorkflowNode(
            id="notify_start",
            name="Notify Start",
            type=WorkflowNodeType.NOTIFICATION.value,
            inputs={"message": "Development startup sequence initiated.", "topic": "WorkflowNotification"},
        )
        n_mission = WorkflowNode(
            id="run_health_mission",
            name="Health Check Mission",
            type=WorkflowNodeType.MISSION.value,
            depends_on=["notify_start"],
            inputs={
                "name": "Dev Health Check",
                "description": "Verify all development services are healthy",
                "priority": "HIGH",
                "type": "SYSTEM",
            },
        )
        n_desktop = WorkflowNode(
            id="open_dev_folder",
            name="Open Dev Folder",
            type=WorkflowNodeType.DESKTOP_ACTION.value,
            depends_on=["run_health_mission"],
            inputs={"action": "open_folder", "folder_path": "/home/warlock"},
        )
        n_done = WorkflowNode(
            id="notify_done",
            name="Notify Complete",
            type=WorkflowNodeType.NOTIFICATION.value,
            depends_on=["open_dev_folder"],
            inputs={"message": "Development environment ready.", "topic": "WorkflowNotification"},
        )
        nodes = {n.id: n for n in [n_notify, n_mission, n_desktop, n_done]}

    # -----------------------------------------------------------------
    # Template: Knowledge Sync Pipeline
    # -----------------------------------------------------------------
    elif template_id == "knowledge_sync":
        n_query = WorkflowNode(
            id="knowledge_query",
            name="Query Knowledge Base",
            type=WorkflowNodeType.KNOWLEDGE_QUERY.value,
            inputs={"query": variables.get("query", "Summarise recent workspace changes"), "top_k": 5},
        )
        n_llm = WorkflowNode(
            id="llm_summarise",
            name="LLM Summarisation",
            type=WorkflowNodeType.LLM_PROMPT.value,
            depends_on=["knowledge_query"],
            inputs={
                "prompt": "Summarise the following knowledge results in 3 bullet points:\n{{ nodes.knowledge_query.outputs.results }}",
            },
        )
        n_notify = WorkflowNode(
            id="notify_complete",
            name="Notify Sync Complete",
            type=WorkflowNodeType.NOTIFICATION.value,
            depends_on=["llm_summarise"],
            inputs={"message": "Knowledge sync complete. Summary: {{ nodes.llm_summarise.outputs.response }}", "topic": "KnowledgeSynced"},
        )
        nodes = {n.id: n for n in [n_query, n_llm, n_notify]}

    # -----------------------------------------------------------------
    # Template: Desktop Automation Demo
    # -----------------------------------------------------------------
    elif template_id == "desktop_automation_demo":
        n1 = WorkflowNode(
            id="notify_start",
            name="Start Notification",
            type=WorkflowNodeType.NOTIFICATION.value,
            inputs={"message": "Desktop automation demo starting.", "topic": "WorkflowNotification"},
        )
        n2 = WorkflowNode(
            id="desktop_notify",
            name="Desktop Notification",
            type=WorkflowNodeType.DESKTOP_ACTION.value,
            depends_on=["notify_start"],
            inputs={"action": "show_notification", "message": "ORION Workflow Active", "title": "ORION"},
        )
        n3 = WorkflowNode(
            id="open_folder",
            name="Open Home Folder",
            type=WorkflowNodeType.DESKTOP_ACTION.value,
            depends_on=["desktop_notify"],
            inputs={"action": "open_folder", "folder_path": "/home/warlock"},
        )
        n4 = WorkflowNode(
            id="clipboard_write",
            name="Write Clipboard",
            type=WorkflowNodeType.DESKTOP_ACTION.value,
            depends_on=["open_folder"],
            inputs={"action": "write_clipboard", "text": "ORION Workflow Engine v3.4"},
        )
        n5 = WorkflowNode(
            id="delay",
            name="Wait 2s",
            type=WorkflowNodeType.DELAY.value,
            flow_type=WorkflowFlowType.DELAY,
            depends_on=["clipboard_write"],
            inputs={"seconds": 2},
            delay_seconds=2.0,
        )
        n6 = WorkflowNode(
            id="notify_done",
            name="Demo Complete",
            type=WorkflowNodeType.NOTIFICATION.value,
            depends_on=["delay"],
            inputs={"message": "Desktop automation demo complete.", "topic": "WorkflowNotification"},
        )
        nodes = {n.id: n for n in [n1, n2, n3, n4, n5, n6]}

    # -----------------------------------------------------------------
    # Template: Health Check Pipeline
    # -----------------------------------------------------------------
    elif template_id == "health_check_pipeline":
        n_mission = WorkflowNode(
            id="health_mission",
            name="Run Health Check Mission",
            type=WorkflowNodeType.MISSION.value,
            inputs={
                "name": "System Health Check",
                "description": "Full kernel and subsystem health probe",
                "priority": "NORMAL",
                "type": "SYSTEM",
            },
        )
        n_condition = WorkflowNode(
            id="health_condition",
            name="Evaluate Health Result",
            type=WorkflowNodeType.CONDITION.value,
            flow_type=WorkflowFlowType.CONDITIONAL,
            depends_on=["health_mission"],
            condition=ConditionConfig(
                type="status_check",
                params={"node_id": "health_mission", "status": "COMPLETED"},
                on_true="notify_healthy",
                on_false="notify_unhealthy",
            ),
            on_success="notify_healthy",
            on_failure="notify_unhealthy",
        )
        n_ok = WorkflowNode(
            id="notify_healthy",
            name="Notify: Healthy",
            type=WorkflowNodeType.NOTIFICATION.value,
            inputs={"message": "All systems healthy.", "topic": "HealthOK"},
        )
        n_fail = WorkflowNode(
            id="notify_unhealthy",
            name="Notify: Unhealthy",
            type=WorkflowNodeType.NOTIFICATION.value,
            inputs={"message": "System health check failed. Review logs.", "topic": "HealthAlert"},
        )
        nodes = {n.id: n for n in [n_mission, n_condition, n_ok, n_fail]}

    else:
        return None

    return Workflow(
        id=workflow_id,
        name=name,
        description=description,
        flow_type=template.flow_type,
        template_id=template_id,
        tags=template.tags,
        nodes=nodes,
        status=WorkflowStatus.PENDING,
        variables=variables,
        metadata={"template_id": template_id},
    )
