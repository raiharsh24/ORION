import asyncio
from typing import Dict, Any, Optional, Set

DESTRUCTIVE_ACTIONS: Set[str] = {
    "delete", "rm", "remove", "destroy", "wipe", "format",
    "overwrite", "write", "mv", "move", "rename",
    "shutdown", "reboot", "restart",
    "install", "uninstall",
    "close_application", "close_app",
    "mouse_click", "mouse_double_click", "mouse_right_click",
    "mouse_drag_drop", "keyboard_type", "keyboard_shortcut",
    "key_press", "window_focus", "window_resize",
    "file_explorer_open", "open_folder",
}


class ConfirmationPolicy:
    """
    Manages interactive validation loops for destructive tasks.
    Supports approve, deny, and timeout flows for human-in-the-loop confirmation.
    """
    def __init__(self) -> None:
        self._destructive_actions = DESTRUCTIVE_ACTIONS
        self._pending_confirmations: Dict[str, asyncio.Future] = {}
        self._default_timeout: float = 30.0

    async def requires_confirmation(self, action: str, args: Dict[str, Any]) -> bool:
        action_lower = action.lower()
        if action_lower in self._destructive_actions:
            return True
        op = str(args.get("op", args.get("operation", ""))).lower()
        if op in self._destructive_actions:
            return True
        cmd = str(args.get("cmd", args.get("command", ""))).lower()
        for keyword in self._destructive_actions:
            if keyword in cmd:
                return True
        return False

    async def request_confirmation(self, confirmation_id: str, timeout: Optional[float] = None) -> bool:
        fut = asyncio.Future()
        self._pending_confirmations[confirmation_id] = fut
        try:
            result = await asyncio.wait_for(fut, timeout=timeout or self._default_timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_confirmations.pop(confirmation_id, None)
            return False

    def approve(self, confirmation_id: str) -> bool:
        fut = self._pending_confirmations.get(confirmation_id)
        if fut and not fut.done():
            fut.set_result(True)
            self._pending_confirmations.pop(confirmation_id, None)
            return True
        return False

    def deny(self, confirmation_id: str) -> bool:
        fut = self._pending_confirmations.get(confirmation_id)
        if fut and not fut.done():
            fut.set_result(False)
            self._pending_confirmations.pop(confirmation_id, None)
            return True
        return False

    def timeout(self, confirmation_id: str) -> bool:
        fut = self._pending_confirmations.get(confirmation_id)
        if fut and not fut.done():
            fut.set_exception(asyncio.TimeoutError())
            self._pending_confirmations.pop(confirmation_id, None)
            return True
        return False

    def is_pending(self, confirmation_id: str) -> bool:
        return confirmation_id in self._pending_confirmations

    def pending_count(self) -> int:
        return len(self._pending_confirmations)

    def list_pending(self) -> list:
        return list(self._pending_confirmations.keys())

    async def set_timeout(self, seconds: float) -> None:
        self._default_timeout = max(1.0, seconds)
