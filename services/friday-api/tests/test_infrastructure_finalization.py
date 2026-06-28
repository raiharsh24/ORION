import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.kernel import FridayKernel
from app.kernel.state import KernelState

client = TestClient(app)

async def ensure_booted():
    kernel = FridayKernel.get_instance()
    if kernel._state in (KernelState.STOPPED, KernelState.ERROR):
        kernel._state = KernelState.STOPPED  # Reset from error state if any
        kernel._config.api_keys.gemini_api_key = "dummy-key"
        await kernel.boot()

@pytest.mark.anyio
async def test_module_lifecycle_registrations():
    await ensure_booted()
    kernel = FridayKernel.get_instance()
    module_registry = kernel.module_registry
    
    # Check registration of all DI singletons as first-class modules
    assert module_registry.get_module("agent_scheduler") is not None
    assert module_registry.get_module("agent_message_bus") is not None
    assert module_registry.get_module("agent_registry") is not None
    assert module_registry.get_module("agent_telemetry") is not None
    assert module_registry.get_module("shared_context") is not None
    assert module_registry.get_module("telemetry") is not None
    assert module_registry.get_module("history") is not None
    assert module_registry.get_module("workflow_history") is not None
    assert module_registry.get_module("workflow_persistence") is not None
    assert module_registry.get_module("checkpoint_manager") is not None
    assert module_registry.get_module("workflow_worker_agent") is not None
    assert module_registry.get_module("workflow_runtime_executor") is not None
    assert module_registry.get_module("runtime_scheduler_bridge") is not None

@pytest.mark.anyio
async def test_cancellation_endpoint():
    await ensure_booted()
    kernel = FridayKernel.get_instance()
    
    # Mock runtime_scheduler_bridge
    mock_bridge = AsyncMock()
    mock_bridge.cancel.return_value = True
    
    # Save original service reference
    original_bridge = kernel.container.get("runtime_scheduler_bridge")
    kernel.container._singletons["runtime_scheduler_bridge"] = mock_bridge
    
    try:
        response = client.post("/workflows/runtime/wf-12345/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workflow_id"] == "wf-12345"
        assert "Runtime" in data["message"]
        
        mock_bridge.cancel.assert_called_once_with("wf-12345")
    finally:
        # Restore original bridge
        kernel.container._singletons["runtime_scheduler_bridge"] = original_bridge

@pytest.mark.anyio
async def test_kernel_teardown_and_agent_cleanup():
    await ensure_booted()
    kernel = FridayKernel.get_instance()
    
    agent_registry = kernel.container.get("agent_registry")
    mock_agent = AsyncMock()
    mock_agent.agent_id = "test-mock-agent-lifecycle"
    mock_agent.name = "Mock Agent"
    mock_agent.capabilities = []
    mock_agent.permissions = []
    
    # Register the mock agent
    await agent_registry.register(mock_agent)
    assert mock_agent.agent_id in agent_registry._agents
    
    # Shutdown coordinator (which handles unregistration and agent cleanup)
    coordinator = kernel.container.get("agent_coordinator")
    await coordinator.shutdown()
    
    # Assert agent is unregistered and shutdown was called on it
    assert mock_agent.shutdown.call_count >= 1
    assert mock_agent.agent_id not in agent_registry._agents
