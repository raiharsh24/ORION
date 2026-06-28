from typing import Dict, Any, Set

DESTRUCTIVE_ACTIONS: Set[str] = {
    "delete", "rm", "remove", "destroy", "wipe", "format",
    "overwrite", "write", "mv", "move", "rename",
    "shutdown", "reboot", "restart",
    "install", "uninstall",
}


class ConfirmationPolicy:
    """
    Manages interactive validation loops for destructive tasks.
    """
    def __init__(self) -> None:
        self._destructive_actions = DESTRUCTIVE_ACTIONS

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
