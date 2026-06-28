import pytest
import anyio
import os
from typing import Dict, Any

from app.orion.capability_registry import CapabilityRegistry, CapabilityMetadata
from app.orion.tool_resolver import ToolResolver, ToolValidator
from app.orion.tool_permission import PermissionManager
from app.orion.tool_sandbox import SandboxManager, SandboxViolation
from app.orion.tool_engine import ToolEngine, ToolExecutionResult
from app.orion.executor import ToolExecutor
from app.events.bus import EventBus
from app.kernel import OrionKernel, OrionKernelConfig
from app.orion.planner import ToolPlan

# ----------------------------------------------------
# 1. Subsystem Component Unit Tests
# ----------------------------------------------------
def test_capability_registry():
    registry = CapabilityRegistry()
    assert "filesystem" in registry.list_capabilities()
    assert "terminal" in registry.list_capabilities()
    
    # Custom plugin registration
    custom = CapabilityMetadata(
        id="vision", name="Vision Analyzer",
        description="Inspects image objects.", category="plugin"
    )
    registry.register_capability(custom)
    assert registry.get_capability("vision") is not None
    assert registry.get_capability("vision").name == "Vision Analyzer"
    
    registry.unregister_capability("vision")
    assert registry.get_capability("vision") is None

def test_tool_validator():
    validator = ToolValidator()
    assert validator.validate_args("filesystem", {"op": "read"}) is True
    assert validator.validate_args("filesystem", {"op": "invalid"}) is False
    assert validator.validate_args("terminal", {"cmd": "ls"}) is True
    assert validator.validate_args("terminal", {"cmd": ""}) is False

def test_permission_manager_hmac():
    pm = PermissionManager()
    cap = CapabilityMetadata(
        id="filesystem", name="FS", description="desc",
        permissions="Dangerous", required_confirmation="DangerousOnly"
    )
    
    # Access rights check
    assert pm.check_permission(cap, "Developer") is True
    assert pm.check_permission(cap, "Guest") is False
    
    # Confirmation policy checks
    assert pm.requires_confirmation(cap, {"op": "delete"}) is True
    assert pm.requires_confirmation(cap, {"op": "read"}) is False
    
    # Token matching checks
    args = {"op": "delete", "path": "file.txt"}
    token = pm.generate_token("filesystem", args)
    assert pm.validate_token("filesystem", args, token) is True
    # Replay protection
    assert pm.validate_token("filesystem", args, token) is False

def test_sandbox_validation():
    sandbox = SandboxManager(workspace_root="/home/warlock/ORION")
    
    # Command patterns
    sandbox.validate_command("ls -la")
    with pytest.raises(SandboxViolation):
        sandbox.validate_command("rm -rf /")
        
    # Boundary paths
    sandbox.validate_path("/home/warlock/ORION/src/main.py")
    with pytest.raises(SandboxViolation):
        sandbox.validate_path("/etc/passwd")

# ----------------------------------------------------
# 2. Subsystem Lifecycle & Health Integration Tests
# ----------------------------------------------------
@pytest.mark.anyio
async def test_tool_engine_integration_and_events():
    OrionKernel.reset_instance()
    kernel = OrionKernel.get_instance(OrionKernelConfig())
    await kernel.boot()
    
    engine = kernel.get_service("tool_engine")
    assert engine is not None
    assert isinstance(engine, ToolEngine)
    
    # Verify health aggregation
    h = engine.health()
    assert h["status"] == "HEALTHY"
    assert "execution_count" in h["details"]
    
    # Register events subscriber logger
    event_bus = kernel.get_service("event_bus")
    events = []
    event_bus.subscribe("ToolExecuted", lambda e: events.append(e))
    event_bus.subscribe("ConfirmationRequested", lambda e: events.append(e))
    event_bus.subscribe("SandboxViolation", lambda e: events.append(e))
    
    # 1. Run filesystem command (without confirmation required)
    res1 = await engine._manager.execute_tool("filesystem", {"op": "list"})
    assert res1.success is True
    
    # 2. Run dangerous command (requiring confirmation)
    res2 = await engine._manager.execute_tool("filesystem", {"op": "delete", "path": "test.txt"}, confirmed=False)
    assert res2.confirmation_required is True
    assert res2.confirmation_token is not None
    
    # 3. Violate sandbox boundaries
    res3 = await engine._manager.execute_tool("filesystem", {"op": "read", "path": "/etc/shadow"})
    assert res3.success is False
    assert "Security Sandbox" in res3.error
    
    await anyio.sleep(0.1)
    topics = [e.topic for e in events]
    assert "ToolExecuted" in topics
    assert "ConfirmationRequested" in topics
    assert "SandboxViolation" in topics
    
    await kernel.shutdown()

@pytest.mark.anyio
async def test_legacy_executor_adapter():
    OrionKernel.reset_instance()
    kernel = OrionKernel.get_instance(OrionKernelConfig())
    await kernel.boot()
    
    tool_registry = kernel.get_service("tool_registry")
    executor = ToolExecutor(tool_registry)
    
    plan = ToolPlan(tool_name="filesystem", args={"op": "list"}, reasoning="List folder content")
    res = await executor.execute(plan)
    assert res.success is True
    assert res.tool == "filesystem"
    
    await kernel.shutdown()
