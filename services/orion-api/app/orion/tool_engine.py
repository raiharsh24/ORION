import time
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from pydantic import BaseModel

from app.orion.capability_registry import CapabilityRegistry, CapabilityMetadata
from app.orion.tool_resolver import ToolResolver, ToolValidator
from app.orion.tool_permission import PermissionManager
from app.orion.tool_sandbox import SandboxManager, SandboxViolation
from app.events.events import OrionEvent

# Re-use or declare compatibility schema
class ToolExecutionResult(BaseModel):
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

# Specific EventBus payload subclasses
class ToolRegistered(OrionEvent):
    def __init__(self, tool_name: str) -> None:
        super().__init__(topic="ToolRegistered", data={"tool": tool_name})

class ToolExecuted(OrionEvent):
    def __init__(self, tool_name: str, duration: float) -> None:
        super().__init__(topic="ToolExecuted", data={"tool": tool_name, "duration": duration})

class ToolFailed(OrionEvent):
    def __init__(self, tool_name: str, error: str) -> None:
        super().__init__(topic="ToolFailed", data={"tool": tool_name, "error": error})

class PermissionDenied(OrionEvent):
    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(topic="PermissionDenied", data={"tool": tool_name, "reason": reason})

class ConfirmationRequested(OrionEvent):
    def __init__(self, tool_name: str, token: str) -> None:
        super().__init__(topic="ConfirmationRequested", data={"tool": tool_name, "token": token})

class CapabilityAdded(OrionEvent):
    def __init__(self, cap_id: str) -> None:
        super().__init__(topic="CapabilityAdded", data={"capability_id": cap_id})

class CapabilityRemoved(OrionEvent):
    def __init__(self, cap_id: str) -> None:
        super().__init__(topic="CapabilityRemoved", data={"capability_id": cap_id})

class SandboxViolationEvent(OrionEvent):
    def __init__(self, tool_name: str, detail: str) -> None:
        super().__init__(topic="SandboxViolation", data={"tool": tool_name, "detail": detail})

class ExecutionManager:
    """
    Orchestrates validation, permissions checks, confirmation logic,
    and sandboxed execution.
    """
    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        tool_resolver: ToolResolver,
        tool_validator: ToolValidator,
        permission_manager: PermissionManager,
        sandbox_manager: SandboxManager,
        event_bus: Optional[Any] = None
    ) -> None:
        self.capability_registry = capability_registry
        self.tool_resolver = tool_resolver
        self.tool_validator = tool_validator
        self.permission_manager = permission_manager
        self.sandbox_manager = sandbox_manager
        self.event_bus = event_bus
        
        # Metrics
        self.execution_count = 0
        self.execution_latency_sum = 0.0
        self.permission_failures = 0
        self.sandbox_violations = 0
        self.timeouts_count = 0
        self.active_executions = 0

    def _safe_publish(self, event: OrionEvent) -> None:
        if not self.event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self.event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.event_bus.publish(event))
                except RuntimeError:
                    asyncio.run(self.event_bus.publish(event))
            else:
                self.event_bus.publish(event)
        except Exception as e:
            logger.error(f"Failed to publish event to EventBus: {str(e)}")

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        confirmed: bool = False,
        confirmation_token: Optional[str] = None,
        user_role: str = "Developer"
    ) -> ToolExecutionResult:
        start_time = time.time()
        self.execution_count += 1
        self.active_executions += 1
        tool_output = ""
        
        try:
            # 1. Lookup Capability metadata
            cap = self.capability_registry.get_capability(tool_name)
            if not cap:
                logger.error(f"Capability metadata for tool '{tool_name}' not found.")
                err_msg = f"Tool '{tool_name}' capability not registered."
                self._safe_publish(ToolFailed(tool_name=tool_name, error=err_msg))
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=False,
                    operation="execute", output="", error=err_msg
                )
                
            # 2. Lookup Tool instance
            tool = self.tool_resolver.resolve(tool_name)
            if not tool:
                logger.error(f"Tool execution instance '{tool_name}' not resolved.")
                err_msg = f"Tool '{tool_name}' execution instance not registered."
                self._safe_publish(ToolFailed(tool_name=tool_name, error=err_msg))
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=False,
                    operation="execute", output="", error=err_msg
                )

            # 3. Permissions authorization
            has_permission = self.permission_manager.check_permission(cap, user_role)
            if not has_permission:
                self.permission_failures += 1
                logger.error(f"Permission denied: role '{user_role}' denied access to capability '{tool_name}'.")
                self._safe_publish(PermissionDenied(tool_name=tool_name, reason="Insufficient permissions"))
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=False,
                    operation="execute", output="", error="Access Denied: Insufficient role credentials."
                )

            # 4. Command & Path Sandboxing check
            try:
                if tool_name == "terminal":
                    cmd = args.get("cmd", "")
                    self.sandbox_manager.validate_command(cmd)
                elif tool_name == "filesystem":
                    path = args.get("path", "")
                    self.sandbox_manager.validate_path(path)
            except SandboxViolation as sv:
                self.sandbox_violations += 1
                self._safe_publish(SandboxViolationEvent(tool_name=tool_name, detail=str(sv)))
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=False,
                    operation="execute", output="", error=str(sv)
                )

            # 5. Arguments check
            if not self.tool_validator.validate_args(tool_name, args):
                err_msg = f"Argument validation failed for tool '{tool_name}'."
                self._safe_publish(ToolFailed(tool_name=tool_name, error=err_msg))
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=False,
                    operation="execute", output="", error=err_msg
                )

            # 6. Policy confirmations checks
            requires_conf = self.permission_manager.requires_confirmation(cap, args)
            if requires_conf:
                if not confirmed:
                    token = self.permission_manager.generate_token(tool_name, args)
                    self._safe_publish(ConfirmationRequested(tool_name=tool_name, token=token))
                    
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
                        tool=tool_name, tool_name=tool_name, success=False,
                        operation=args.get("op", "execute"), output=desc,
                        confirmation_required=True, confirmation_token=token
                    )
                
                # Check validation token match
                if not confirmation_token or not self.permission_manager.validate_token(tool_name, args, confirmation_token):
                    return ToolExecutionResult(
                        tool=tool_name, tool_name=tool_name, success=False,
                        operation=args.get("op", "execute"), output="",
                        error="Security Alert: Invalid or expired confirmation token."
                    )

            # 7. Safe timed execution
            try:
                logger.info(f"Running sandboxed tool '{tool_name}' execution with timeout={cap.timeout}s.")
                output = await asyncio.wait_for(tool.execute(**args), timeout=cap.timeout)
                tool_output = str(output)
                
                duration = (time.time() - start_time) * 1000.0
                self.execution_latency_sum += duration
                self._safe_publish(ToolExecuted(tool_name=tool_name, duration=duration))
                
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=True,
                    operation=args.get("op", "execute"), duration=duration,
                    output=str(output)
                )
            except asyncio.TimeoutError:
                self.timeouts_count += 1
                err_msg = f"Tool '{tool_name}' execution timed out after {cap.timeout} seconds."
                logger.error(err_msg)
                self._safe_publish(ToolFailed(tool_name=tool_name, error=err_msg))
                return ToolExecutionResult(
                    tool=tool_name, tool_name=tool_name, success=False,
                    operation=args.get("op", "execute"), output="", error=err_msg
                )
                
        except Exception as e:
            logger.error(f"Error running tool '{tool_name}': {str(e)}")
            self._safe_publish(ToolFailed(tool_name=tool_name, error=str(e)))
            return ToolExecutionResult(
                tool=tool_name, tool_name=tool_name, success=False,
                operation=args.get("op", "execute"), output="", error=str(e)
            )
        finally:
            self.active_executions -= 1
            self._safe_publish(OrionEvent(topic="ToolCompleted", data={
                "tool_name": tool_name, "output": tool_output
            }))



class ToolEngine:
    """
    Subsystem container service exposing lifecycle hooks and dynamic custom plugins capability injection points.
    """
    def __init__(self) -> None:
        self.capability_registry = CapabilityRegistry()
        self._manager: Optional[ExecutionManager] = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
            
        logger.info("Initializing ToolEngine service...")
        from app.kernel.kernel import OrionKernel
        kernel = OrionKernel.get_instance()
        event_bus = kernel.get_service("event_bus")
        tool_registry = kernel.get_service("tool_registry")
        
        resolver = ToolResolver(tool_registry)
        validator = ToolValidator()
        permission = PermissionManager()
        sandbox = SandboxManager()
        
        self._manager = ExecutionManager(
            capability_registry=self.capability_registry,
            tool_resolver=resolver,
            tool_validator=validator,
            permission_manager=permission,
            sandbox_manager=sandbox,
            event_bus=event_bus
        )
        
        self._event_bus = event_bus
        if self._event_bus:
            self._event_bus.subscribe("PlanValidated", self.on_plan_validated)
            self._event_bus.subscribe("MissionStarted", self.on_mission_started)
            self._event_bus.subscribe("WorkflowStarted", self.on_workflow_started)
            self._event_bus.subscribe("MemoryUpdated", self.on_memory_updated)
            
        self._initialized = True
        logger.info("ToolEngine initialized successfully.")

    async def start(self) -> None:
        logger.info("ToolEngine service started.")

    async def shutdown(self) -> None:
        logger.info("ToolEngine service shut down.")
        if self._event_bus:
            self._event_bus.unsubscribe("PlanValidated", self.on_plan_validated)
            self._event_bus.unsubscribe("MissionStarted", self.on_mission_started)
            self._event_bus.unsubscribe("WorkflowStarted", self.on_workflow_started)
            self._event_bus.unsubscribe("MemoryUpdated", self.on_memory_updated)
        self._initialized = False

    def health(self) -> Dict[str, Any]:
        if not self._initialized or not self._manager:
            return {"status": "WARNING", "message": "ToolEngine is not initialized."}
            
        avg_latency = 0.0
        if self._manager.execution_count > 0:
            avg_latency = self._manager.execution_latency_sum / self._manager.execution_count
            
        return {
            "status": "HEALTHY",
            "message": "ToolEngine operating nominally.",
            "details": {
                "execution_count": self._manager.execution_count,
                "permission_failures": self._manager.permission_failures,
                "sandbox_violations": self._manager.sandbox_violations,
                "timeouts_count": self._manager.timeouts_count,
                "active_executions": self._manager.active_executions,
                "average_execution_latency_ms": round(avg_latency, 2)
            }
        }

    # ==========================================
    # Dynamic Plugin Registration Hook Interfaces
    # ==========================================
    def register_capability(self, metadata: CapabilityMetadata) -> None:
        self.capability_registry.register_capability(metadata)
        if self._manager and self._manager.event_bus:
            self._manager._safe_publish(CapabilityAdded(cap_id=metadata.id))

    def unregister_capability(self, capability_id: str) -> None:
        self.capability_registry.unregister_capability(capability_id)
        if self._manager and self._manager.event_bus:
            self._manager._safe_publish(CapabilityRemoved(cap_id=capability_id))

    # EventBus callbacks
    def on_plan_validated(self, event: OrionEvent) -> None:
        plan_data = event.data if hasattr(event, "data") else {}
        tool_name = plan_data.get("tool_name") or plan_data.get("tool") or ""
        steps = plan_data.get("steps") or []
        logger.info(f"ToolEngine: PlanValidated for tool='{tool_name}' with {len(steps)} steps")
        if tool_name and self._manager:
            cap = self.capability_registry.get_capability(tool_name)
            if not cap:
                logger.debug(f"ToolEngine: capability '{tool_name}' not yet registered, preparing for lazy registration")

    def on_mission_started(self, event: OrionEvent) -> None:
        data = event.data if hasattr(event, "data") else {}
        mission_id = data.get("mission_id") or data.get("id", "")
        logger.info(f"ToolEngine: MissionStarted '{mission_id}', activating tool context")

    def on_workflow_started(self, event: OrionEvent) -> None:
        data = event.data if hasattr(event, "data") else {}
        workflow_id = data.get("workflow_id", "")
        step_count = data.get("steps", data.get("step_count", 0))
        logger.info(f"ToolEngine: WorkflowStarted '{workflow_id}' ({step_count} steps), preparing tool environment")

    def on_memory_updated(self, event: OrionEvent) -> None:
        data = event.data if hasattr(event, "data") else {}
        layer = data.get("layer", "")
        key = data.get("key", "")
        logger.info(f"ToolEngine: MemoryUpdated layer='{layer}' key='{key}', refreshing tool context")
