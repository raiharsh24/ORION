from typing import Dict, Any, Optional
from loguru import logger
from app.friday.tool_registry import ToolRegistry
from app.tools.base_tool import BaseTool

class ToolResolver:
    """
    Resolves requested tool names to executable instances.
    """
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._registry = tool_registry

    def resolve(self, tool_name: str) -> Optional[BaseTool]:
        return self._registry.get(tool_name)

class ToolValidator:
    """
    Validates parameter structures and option selections prior to execution.
    """
    def validate_args(self, tool_name: str, args: Dict[str, Any]) -> bool:
        if tool_name == "filesystem":
            op = args.get("op")
            if not op or op not in ["read", "write", "delete", "list"]:
                logger.warning("ToolValidator: invalid filesystem operation.")
                return False
        elif tool_name == "terminal":
            cmd = args.get("cmd")
            if not cmd or not isinstance(cmd, str) or len(cmd.strip()) == 0:
                logger.warning("ToolValidator: empty terminal command.")
                return False
        return True
