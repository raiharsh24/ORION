from typing import Any, Dict, List, Optional
from loguru import logger

from app.friday.planner_schema import ExecutionPlan
from app.goal_planner.models import GoalTask, GoalPlan
from app.workspace.models import WorkspaceContext

_INTENT_TO_CAPABILITY: Dict[str, str] = {
    "desktop": "desktop",
    "browser": "browser",
    "terminal": "terminal",
    "coding": "filesystem",
    "filesystem": "filesystem",
    "search": "search",
    "workflow": "workflow",
    "planning": "planning",
    "memory": "memory",
    "vision": "vision",
    "conversation": "",
    "chat": "",
    "web_search": "browser",
    "file_operation": "filesystem",
    "system_command": "terminal",
    "open_app": "desktop",
    "plugin": "workflow",
    "vision_action": "vision",
    "search_memory": "memory",
    "autonomous_goal": "workflow",
}

_TASK_ACTION_MAP: Dict[str, tuple] = {
    "browser": ("browse_page", "Navigate to or interact with a web page"),
    "filesystem": ("file_operation", "Read, write, or list files on disk"),
    "terminal": ("run_command", "Execute a shell command"),
    "desktop": ("desktop_action", "Perform a desktop UI action"),
    "search": ("web_search", "Search the web for information"),
    "workflow": ("run_workflow", "Execute a multi-step workflow"),
    "planning": ("create_plan", "Create or refine a plan"),
    "memory": ("memory_op", "Access or store in memory"),
    "vision": ("vision_op", "Analyze screen content or images"),
}


class GoalPlanner:
    def __init__(self) -> None:
        self._task_counter = 0

    def _next_id(self) -> str:
        self._task_counter += 1
        return f"task_{self._task_counter}"

    def _get_intent_str(self, intent: Any) -> str:
        if hasattr(intent, "value"):
            return intent.value.lower()
        return str(intent).lower()

    def create_goal_plan(
        self,
        prompt: str,
        intent: Any,
        plan: Optional[ExecutionPlan] = None,
        workspace: Optional[WorkspaceContext] = None,
    ) -> GoalPlan:
        self._task_counter = 0

        goal_desc = plan.goal if plan and plan.goal else prompt[:120]
        intent_str = self._get_intent_str(intent)
        capabilities = plan.capabilities if plan else []

        # Enrich capabilities from workspace context
        if workspace:
            enriched = self._enrich_capabilities(capabilities, workspace)
            if enriched:
                logger.info(
                    f"GoalPlanner: enriched capabilities via workspace "
                    f"(framework={workspace.framework}, languages={workspace.detected_languages}): "
                    f"added {enriched}"
                )
                for cap in enriched:
                    if cap not in capabilities:
                        capabilities.append(cap)

        goal_plan = GoalPlan(
            goal=goal_desc,
            intent=intent_str,
        )

        if intent_str in ("conversation", "chat", "unknown"):
            if not capabilities:
                logger.info("GoalPlanner: no tasks needed for conversation/unknown intent")
                return goal_plan

        steps = plan.steps if plan and hasattr(plan, "steps") and plan.steps else []

        if steps:
            self._build_multi_step_tasks(goal_plan, steps, capabilities, intent_str)
        else:
            self._build_single_step_tasks(goal_plan, capabilities, intent_str)

        logger.info(
            f"GoalPlanner: created {goal_plan.task_count} task(s) "
            f"for intent={intent_str}, goal=\"{goal_desc[:60]}...\""
        )
        for t in goal_plan.tasks:
            deps = f" deps={t.dependencies}" if t.dependencies else ""
            par = f" group={t.parallel_group}" if t.parallel_group else ""
            logger.info(
                f"  Task {t.id}: {t.title} [{t.required_capability}]"
                f"(complexity={t.estimated_complexity}){deps}{par}"
            )

        return goal_plan

    def _build_single_step_tasks(
        self,
        goal_plan: GoalPlan,
        capabilities: List[str],
        intent_str: str,
    ) -> None:
        caps = capabilities or [intent_str] if intent_str else []
        for cap in caps:
            task_info = _TASK_ACTION_MAP.get(cap, (cap, f"Perform {cap} operation"))
            task = GoalTask(
                id=self._next_id(),
                title=task_info[0],
                description=task_info[1],
                required_capability=cap,
                estimated_complexity=1.0,
            )
            goal_plan.tasks.append(task)

    def _build_multi_step_tasks(
        self,
        goal_plan: GoalPlan,
        steps: List[Dict[str, Any]],
        capabilities: List[str],
        intent_str: str,
    ) -> None:
        prev_task_id: Optional[str] = None
        for i, step in enumerate(steps):
            action = step.get("action", "unknown")
            args = step.get("args", {})
            op = args.get("op", "")

            cap = self._resolve_step_capability(action, op, capabilities, i)
            task_info = _TASK_ACTION_MAP.get(
                cap, (cap or action, f"Step {i + 1}: {action}")
            )

            deps = [prev_task_id] if prev_task_id is not None else []

            has_search = "search" in action.lower() or op == "search"
            is_memory = "memory" in cap

            parallel_group = None
            if prev_task_id is not None and not deps:
                pass
            elif prev_task_id is not None and not is_memory and not has_search:
                for prev_step in steps[max(0, i - 2):i]:
                    prev_op = prev_step.get("args", {}).get("op", "")
                    if prev_op and prev_op != op:
                        parallel_group = f"group_{i // 2}"

            task = GoalTask(
                id=self._next_id(),
                title=task_info[0],
                description=f"{task_info[1]}: {action}",
                required_capability=cap,
                dependencies=deps,
                estimated_complexity=1.0,
                parallel_group=parallel_group,
            )
            goal_plan.tasks.append(task)
            prev_task_id = task.id

    def _enrich_capabilities(
        self,
        base_capabilities: List[str],
        workspace: WorkspaceContext,
    ) -> List[str]:
        enriched: List[str] = []

        framework = workspace.framework.lower() if workspace.framework else ""
        languages = [lang.lower() for lang in workspace.detected_languages]
        project_type = workspace.project_type.lower() if workspace.project_type else ""

        # Framework→capability mappings
        framework_caps = {
            "react": ["browser", "filesystem"],
            "vue": ["browser", "filesystem"],
            "angular": ["browser", "filesystem"],
            "svelte": ["browser", "filesystem"],
            "next.js": ["browser", "filesystem"],
            "nuxt": ["browser", "filesystem"],
            "django": ["terminal", "filesystem"],
            "flask": ["terminal", "filesystem"],
            "fastapi": ["terminal", "filesystem"],
            "express": ["terminal", "filesystem"],
            "rails": ["terminal", "filesystem"],
            "spring": ["terminal", "filesystem"],
        }

        if framework in framework_caps:
            enriched.extend(framework_caps[framework])

        # Language→capability mappings
        language_caps = {
            "python": ["terminal", "filesystem"],
            "javascript": ["browser", "filesystem"],
            "typescript": ["browser", "filesystem"],
            "go": ["terminal", "filesystem"],
            "rust": ["terminal", "filesystem"],
            "java": ["terminal", "filesystem"],
        }
        for lang in languages:
            if lang in language_caps:
                for cap in language_caps[lang]:
                    if cap not in enriched:
                        enriched.append(cap)

        # Project type→capability mappings
        if project_type == "frontend":
            if "browser" not in enriched:
                enriched.append("browser")
        elif project_type in ("backend", "fullstack"):
            if "terminal" not in enriched:
                enriched.append("terminal")

        return enriched

    def _resolve_step_capability(
        self,
        action: str,
        op: str,
        capabilities: List[str],
        step_index: int,
    ) -> str:
        if op:
            op_to_cap = {
                "read": "filesystem",
                "write": "filesystem",
                "list": "filesystem",
                "delete": "filesystem",
                "search": "search",
                "info": "filesystem",
            }
            cap = op_to_cap.get(op)
            if cap:
                return cap

        if action:
            action_to_cap = {
                "filesystem_op": "filesystem",
                "terminal_exec": "terminal",
                "web_search": "browser",
                "memory_op": "memory",
                "process_prompt": "llm",
                "desktop_action": "desktop",
            }
            cap = action_to_cap.get(action)
            if cap:
                return cap

        if capabilities and step_index < len(capabilities):
            return capabilities[step_index]

        if capabilities:
            return capabilities[0]

        return action
