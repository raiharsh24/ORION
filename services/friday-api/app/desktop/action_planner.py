import time
from typing import Dict, Any, List, Optional
from loguru import logger


class DesktopActionPlanner:
    def __init__(self, vision_engine: Any = None, desktop_controller: Any = None) -> None:
        self._vision_engine = vision_engine
        self._desktop_controller = desktop_controller
        self._action_templates: Dict[str, Dict[str, Any]] = {
            "click": {
                "action": "mouse_click",
                "description": "Click at screen coordinates",
                "params": {"x": "int", "y": "int", "button": "str (optional, default: left)"},
            },
            "double_click": {
                "action": "mouse_double_click",
                "description": "Double-click at screen coordinates",
                "params": {"x": "int", "y": "int"},
            },
            "right_click": {
                "action": "mouse_right_click",
                "description": "Right-click at screen coordinates",
                "params": {"x": "int", "y": "int"},
            },
            "type_text": {
                "action": "keyboard_type",
                "description": "Type text into the focused element",
                "params": {"text": "str"},
            },
            "press_key": {
                "action": "key_press",
                "description": "Press a single keyboard key",
                "params": {"key": "str"},
            },
            "hotkey": {
                "action": "keyboard_shortcut",
                "description": "Execute a keyboard shortcut",
                "params": {"combo": "str (e.g. ctrl+c)"},
            },
            "drag_drop": {
                "action": "mouse_drag_drop",
                "description": "Drag from one position to another",
                "params": {"start_x": "int", "start_y": "int", "end_x": "int", "end_y": "int"},
            },
            "open_app": {
                "action": "open_application",
                "description": "Open an application",
                "params": {"app_name": "str"},
            },
            "close_app": {
                "action": "close_application",
                "description": "Close an application",
                "params": {"app_name": "str"},
            },
            "screenshot": {
                "action": "take_screenshot",
                "description": "Take a screenshot",
                "params": {},
            },
            "focus_window": {
                "action": "window_focus",
                "description": "Focus a window by name",
                "params": {"window_name": "str"},
            },
        }

    async def plan_from_goal(
        self,
        goal: str,
        screen_context: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        steps = self._generate_steps(goal, screen_context, available_tools)
        duration_ms = (time.perf_counter() - start) * 1000
        return {
            "plan_id": f"plan_{int(time.time())}",
            "goal": goal,
            "steps": steps,
            "step_count": len(steps),
            "duration_ms": round(duration_ms, 1),
        }

    def _generate_steps(
        self,
        goal: str,
        screen_context: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        goal_lower = goal.lower()
        steps: List[Dict[str, Any]] = []
        elements = (screen_context or {}).get("ui_elements", [])

        if "click" in goal_lower or "press" in goal_lower or "select" in goal_lower:
            target = self._find_target_element(goal, elements)
            if target:
                steps.append({
                    "order": 1,
                    "action": "mouse_move",
                    "params": {"x": target["bbox"]["x"], "y": target["bbox"]["y"]},
                    "description": f"Move mouse to {target.get('text', 'target')}",
                })
                steps.append({
                    "order": 2,
                    "action": "mouse_click",
                    "params": {"button": "left"},
                    "description": f"Click on {target.get('text', 'target')}",
                })

        elif "type" in goal_lower or "write" in goal_lower or "enter" in goal_lower:
            target = self._find_target_element(goal, elements, preferred_type="input")
            if target:
                steps.append({
                    "order": 1,
                    "action": "mouse_move",
                    "params": {"x": target["bbox"]["x"], "y": target["bbox"]["y"]},
                    "description": f"Move mouse to input field",
                })
                steps.append({
                    "order": 2,
                    "action": "mouse_click",
                    "params": {"button": "left"},
                    "description": "Focus input field",
                })

            text_to_type = self._extract_text_to_type(goal)
            if text_to_type:
                steps.append({
                    "order": 3,
                    "action": "keyboard_type",
                    "params": {"text": text_to_type},
                    "description": f"Type: {text_to_type}",
                })

        elif "open" in goal_lower or "launch" in goal_lower or "start" in goal_lower:
            app_name = self._extract_app_name(goal)
            steps.append({
                "order": 1,
                "action": "open_application",
                "params": {"app_name": app_name or goal},
                "description": f"Open {app_name or goal}",
            })

        elif "close" in goal_lower or "quit" in goal_lower or "exit" in goal_lower:
            app_name = self._extract_app_name(goal)
            steps.append({
                "order": 1,
                "action": "close_application",
                "params": {"app_name": app_name or goal},
                "description": f"Close {app_name or goal}",
            })

        elif "screenshot" in goal_lower or "capture" in goal_lower:
            steps.append({
                "order": 1,
                "action": "take_screenshot",
                "params": {},
                "description": "Capture screen",
            })

        elif "focus" in goal_lower or "switch" in goal_lower:
            window_name = self._extract_window_name(goal)
            steps.append({
                "order": 1,
                "action": "window_focus",
                "params": {"window_name": window_name or goal},
                "description": f"Focus window: {window_name or goal}",
            })

        if not steps:
            steps.append({
                "order": 1,
                "action": "unknown",
                "params": {},
                "description": f"Could not determine action for: {goal}",
            })

        return steps

    def _find_target_element(
        self, goal: str, elements: List[Dict[str, Any]],
        preferred_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        goal_lower = goal.lower()
        for elem in elements:
            elem_text = (elem.get("text") or "").lower()
            if elem_text and elem_text in goal_lower:
                if preferred_type and elem.get("type") != preferred_type:
                    continue
                return elem
        for elem in elements:
            if preferred_type and elem.get("type") == preferred_type:
                return elem
        return elements[0] if elements else None

    def _extract_text_to_type(self, goal: str) -> Optional[str]:
        import re
        patterns = [
            r'type\s+"([^"]+)"',
            r"type\s+'([^']+)'",
            r'write\s+"([^"]+)"',
            r"write\s+'([^']+)'",
            r'enter\s+"([^"]+)"',
            r"enter\s+'([^']+)'",
        ]
        for pat in patterns:
            m = re.search(pat, goal, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _extract_app_name(self, goal: str) -> Optional[str]:
        import re
        patterns = [
            r'(?:open|launch|start|close|quit|exit)\s+(\w+(?:\s+\w+){0,3})',
        ]
        for pat in patterns:
            m = re.search(pat, goal, re.IGNORECASE)
            if m:
                name = m.group(1)
                stop_words = {"the", "a", "an", "and", "or", "with", "for", "in", "on", "at", "to"}
                parts = name.split()
                filtered = [p for p in parts if p.lower() not in stop_words]
                return " ".join(filtered) if filtered else name
        return None

    def _extract_window_name(self, goal: str) -> Optional[str]:
        import re
        patterns = [
            r'(?:focus|switch\s+to)\s+(\w+(?:\s+\w+){0,3})',
        ]
        for pat in patterns:
            m = re.search(pat, goal, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def list_available_actions(self) -> List[Dict[str, Any]]:
        return [
            {"name": name, **tpl}
            for name, tpl in self._action_templates.items()
        ]
