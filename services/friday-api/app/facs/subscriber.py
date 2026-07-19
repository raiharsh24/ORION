import os
import re
from loguru import logger
from typing import Optional

from app.events.bus import EventBus
from app.events.events import FridayEvent

class FACSSubscriber:
    """
    Subscribes to FRIDAY's EventBus to dynamically update
    the FACS continuity documentation on goals and task completions.
    """
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self.docs_dir = self._find_docs_dir()
        logger.info(f"FACSSubscriber initialized. Docs directory resolved: {self.docs_dir}")

    def _find_docs_dir(self) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root = os.path.abspath(os.path.join(current_dir, "../../../../"))
        return os.path.join(root, "docs")

    async def initialize(self):
        """Binds EventBus event subscriber hooks."""
        if self._event_bus:
            self._event_bus.subscribe("autonomous.goal.created", self.on_goal_created)
            self._event_bus.subscribe("autonomous.goal.status", self.on_goal_status)
            self._event_bus.subscribe("autonomous.task.status", self.on_task_status)
            self._event_bus.subscribe("autonomous.reflection.generated", self.on_reflection_generated)
            logger.info("FACSSubscriber event listeners registered successfully.")

    def on_goal_created(self, event: FridayEvent) -> None:
        goal_id = event.data.get("goal_id")
        prompt = event.data.get("prompt")
        logger.info(f"[FACS] Goal created: {goal_id} - '{prompt}'")
        self._update_project_state(goal_id, prompt, "active")
        self._update_current_sprint(goal_id, f"Autonomous Goal: {prompt}", "active")

    def on_goal_status(self, event: FridayEvent) -> None:
        goal_id = event.data.get("goal_id")
        status = event.data.get("status")
        logger.info(f"[FACS] Goal status changed: {goal_id} to {status}")
        self._update_project_state(goal_id, None, status)

    def on_task_status(self, event: FridayEvent) -> None:
        task_id = event.data.get("task_id")
        status = event.data.get("status")
        logger.info(f"[FACS] Task status changed: {task_id} to {status}")
        self._update_current_sprint(task_id, f"Task {task_id}", status)

    def on_reflection_generated(self, event: FridayEvent) -> None:
        goal_id = event.data.get("goal_id")
        task_id = event.data.get("task_id")
        reflection = event.data.get("reflection", {})
        logger.info(f"[FACS] Reflection generated for task {task_id}")
        self._append_reflection(goal_id, task_id, reflection)

    def _update_project_state(self, goal_id: str, prompt: Optional[str], status: str):
        state_path = os.path.join(self.docs_dir, "PROJECT_STATE.md")
        if not os.path.exists(state_path):
            return

        try:
            with open(state_path, "r") as f:
                content = f.read()

            block_pattern = r"(### Active Autonomous Session.*?)(###|$)"
            goal_block = f"""### Active Autonomous Session
- **Goal ID**: {goal_id}
- **Goal**: {prompt or "N/A"}
- **Session Status**: {status}

"""
            if "Active Autonomous Session" in content:
                content = re.sub(block_pattern, goal_block + r"\2", content, flags=re.DOTALL)
            else:
                content += "\n" + goal_block

            with open(state_path, "w") as f:
                f.write(content)
            logger.info(f"[FACS] Updated PROJECT_STATE.md for goal {goal_id}")
        except Exception as e:
            logger.error(f"[FACS] Failed to update project state doc: {e}")

    def _update_current_sprint(self, task_id: str, description: str, status: str):
        sprint_path = os.path.join(self.docs_dir, "CURRENT_SPRINT.md")
        if not os.path.exists(sprint_path):
            return

        # Determine checkbox type
        box = "[ ]"
        if status in ("in_progress", "active"):
            box = "[/]"
        elif status in ("completed", "done", "success"):
            box = "[x]"

        try:
            with open(sprint_path, "r") as f:
                lines = f.read().splitlines()

            # Find matching line containing task_id
            updated = False
            for idx, line in enumerate(lines):
                if task_id in line or description in line:
                    lines[idx] = f"  - {box} {description} (ID: {task_id})"
                    updated = True
                    break

            if not updated:
                # Find the line after "- [ ] Phase 6 - Validation" to insert tasks dynamically
                insert_idx = len(lines)
                for idx, line in enumerate(lines):
                    if "Phase 6 - Validation" in line:
                        insert_idx = idx + 4
                        break
                lines.insert(insert_idx, f"  - {box} {description} (ID: {task_id})")

            with open(sprint_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            logger.info(f"[FACS] Updated CURRENT_SPRINT.md for task {task_id}")
        except Exception as e:
            logger.error(f"[FACS] Failed to update current sprint doc: {e}")

    def _append_reflection(self, goal_id: str, task_id: str, reflection: dict):
        handoff_path = os.path.join(self.docs_dir, "AI_HANDOFF.md")
        if not os.path.exists(handoff_path):
            return

        summary = reflection.get("summary", "No summary provided.")
        learnings = reflection.get("learnings", [])
        
        reflection_block = f"""
### Automated Reflection (Task: {task_id})
- **Goal ID**: {goal_id}
- **Summary**: {summary}
- **Learnings**:
"""
        for learn in learnings:
            reflection_block += f"  - {learn}\n"

        try:
            with open(handoff_path, "a") as f:
                f.write(reflection_block)
            logger.info(f"[FACS] Appended reflection for task {task_id} to AI_HANDOFF.md")
        except Exception as e:
            logger.error(f"[FACS] Failed to append reflection to handoff doc: {e}")
