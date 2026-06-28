import hmac
import hashlib
import os
import time
import json
from typing import Dict, Any, Optional, List
from loguru import logger
from app.orion.tool_registry import ToolRegistry
from pydantic import BaseModel

# Initialize module-level structures for compatibility
_pending_tokens: set[str] = set()

class ToolExecutionResult(BaseModel):
    """
    Structured results returned from the tool execution stage.
    """
    success: bool
    tool: str
    operation: str = "execute"
    duration: float = 0.0
    warnings: List[str] = []
    artifacts: List[str] = []
    output: str
    confirmation_required: bool = False
    confirmation_token: Optional[str] = None
    error: Optional[str] = None
    tool_name: str = ""

    def model_post_init(self, __context) -> None:
        if not self.tool_name:
            self.tool_name = self.tool
        if not self.tool:
            self.tool = self.tool_name

class ToolExecutor:
    """
    Validates, manages confirmation checks, and executes tools stored in the ToolRegistry.
    Automatically redirects calls to the active Orion ToolEngine.
    """
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    async def execute(
        self,
        plan: Any,
        confirmed: bool = False,
        confirmation_token: Optional[str] = None
    ) -> ToolExecutionResult:
        from app.kernel.kernel import OrionKernel
        kernel = OrionKernel.get_instance()
        tool_engine = kernel.get_service("tool_engine")

        tool_name = getattr(plan, "tool_name", None) or getattr(plan, "tool", None)
        args = getattr(plan, "args", {})

        # If kernel service is loaded, delegate execution to ToolEngine ExecutionManager
        if tool_engine and getattr(tool_engine, "_manager", None):
            res = await tool_engine._manager.execute_tool(
                tool_name=tool_name,
                args=args,
                confirmed=confirmed,
                confirmation_token=confirmation_token
            )
            # Adapt output
            return ToolExecutionResult(
                success=res.success,
                tool=res.tool,
                operation=res.operation,
                duration=res.duration,
                warnings=res.warnings,
                artifacts=res.artifacts,
                output=res.output,
                confirmation_required=res.confirmation_required,
                confirmation_token=res.confirmation_token,
                error=res.error
            )

        # Fallback to local direct execution (e.g. unbooted unit tests)
        logger.warning("ToolEngine not registered in container. Running local execution fallback.")
        from app.orion.tool_permission import PermissionManager
        pm = PermissionManager()

        tool = self.tool_registry.get(tool_name)
        if not tool:
            return ToolExecutionResult(
                success=False, tool=tool_name or "unknown", output="",
                error=f"Tool '{tool_name}' not found in registry."
            )

        requires_conf = False
        if hasattr(tool, "requires_confirmation"):
            requires_conf = tool.requires_confirmation(**args)

        if requires_conf:
            if not confirmed:
                token = pm.generate_token(tool_name, args)
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
                    desc = f"Execution of tool '{tool_name}' requires user confirmation."
                return ToolExecutionResult(
                    success=False, tool=tool_name, output=desc,
                    confirmation_required=True, confirmation_token=token
                )
            if not confirmation_token or not pm.validate_token(tool_name, args, confirmation_token):
                return ToolExecutionResult(
                    success=False, tool=tool_name, output="",
                    error="Security Alert: Invalid or expired confirmation token."
                )

        try:
            output = await tool.execute(**args)
            return ToolExecutionResult(
                success=True, tool=tool_name, output=str(output)
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False, tool=tool_name, output="", error=str(e)
            )
