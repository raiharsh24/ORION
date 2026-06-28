import hashlib
import json
from typing import Dict, Any, Optional
from loguru import logger
from app.orion.tool_registry import ToolRegistry
from app.orion.planner import ToolPlan
from pydantic import BaseModel

class ToolExecutionResult(BaseModel):
    """
    Structured results returned from the tool execution stage.
    """
    tool_name: str
    success: bool
    output: str
    confirmation_required: bool = False
    confirmation_token: Optional[str] = None
    error: Optional[str] = None

class ToolExecutor:
    """
    Validates, manages confirmation checks, and executes tools stored in the ToolRegistry.
    """
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    def generate_token(self, tool_name: str, args: Dict[str, Any]) -> str:
        serialized = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def execute(
        self,
        plan: ToolPlan,
        confirmed: bool = False,
        confirmation_token: Optional[str] = None
    ) -> ToolExecutionResult:
        tool_name = plan.tool_name
        args = plan.args

        tool = self.tool_registry.get(tool_name)
        if not tool:
            logger.error(f"Tool '{tool_name}' not found in registry.")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=f"Tool '{tool_name}' not found in registry."
            )

        # Check if confirmation is required
        requires_conf = False
        try:
            if hasattr(tool, "requires_confirmation"):
                requires_conf = tool.requires_confirmation(**args)
        except Exception as e:
            logger.warning(f"Error checking confirmation for '{tool_name}': {str(e)}")

        if requires_conf and not confirmed:
            token = self.generate_token(tool_name, args)
            logger.info(f"Tool '{tool_name}' requires confirmation. Token generated: {token}")
            
            desc = ""
            if tool_name == "filesystem":
                op = args.get("op")
                path = args.get("path")
                if op == "delete":
                    desc = f"Are you sure you want to delete the file/directory at '{path}'?"
                elif op == "write":
                    desc = f"Are you sure you want to overwrite the file at '{path}'?"
            elif tool_name == "terminal":
                cmd = args.get("cmd")
                desc = f"Are you sure you want to execute this dangerous command in the terminal?\nCommand: '{cmd}'"
            
            if not desc:
                desc = f"Execution of tool '{tool_name}' with args {args} requires user confirmation."

            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output=desc,
                confirmation_required=True,
                confirmation_token=token
            )

        try:
            logger.info(f"Executing tool '{tool_name}' with args: {args}")
            # The tool can be registered as a callable function wrapper or BaseTool subclass instance.
            # In both cases, ToolRegistry guarantees it is a BaseTool exposing the execute() method.
            output = await tool.execute(**args)
            return ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                output=str(output)
            )
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {str(e)}")
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                output="",
                error=str(e)
            )
