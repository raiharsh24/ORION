import pytest
import anyio
from typing import Dict, Any
from app.kernel import (
    OrionKernel, OrionServiceContainer, OrionKernelConfig, KernelState,
    HealthStatus, SubsystemHealth, check_service_health,
    KernelBooting, KernelReady, KernelShutdown, KernelRestart, KernelError
)
from app.events.events import OrionEvent

class MockHealthService:
    def __init__(self, status: str = "HEALTHY", is_async: bool = False):
        self._status = status
        self._is_async = is_async
        self.health_called = 0

    def health(self) -> Any:
        self.health_called += 1
        if self._is_async:
            async def async_health():
                return self._status
            return async_health()
        return self._status

class MockStoppingService:
    def __init__(self):
        self.stop_called = 0

    def stop(self):
        self.stop_called += 1

@pytest.mark.anyio
async def test_kernel_singleton():
    OrionKernel.reset_instance()
    k1 = OrionKernel.get_instance()
    k2 = OrionKernel.get_instance()
    assert k1 is k2
    
    OrionKernel.reset_instance()
    k3 = OrionKernel.get_instance()
    assert k3 is not k1

@pytest.mark.anyio
async def test_service_container():
    container = OrionServiceContainer()
    assert not container.has("dummy")
    
    # 1. Singleton Scope
    service = object()
    container.register_singleton("dummy", service)
    assert container.has("dummy")
    assert container.get("dummy") is service
    assert "dummy" in container.list_services()
    
    # Unregister
    container.unregister("dummy")
    assert not container.has("dummy")
    
    # 2. Lazy Singleton
    eval_count = 0
    def factory():
        nonlocal eval_count
        eval_count += 1
        return "lazy-resolved-service"
        
    container.register_singleton("lazy_svc", factory)
    assert container.has("lazy_svc")
    assert eval_count == 0
    
    res1 = container.get("lazy_svc")
    assert res1 == "lazy-resolved-service"
    assert eval_count == 1
    
    res2 = container.get("lazy_svc")
    assert res2 == "lazy-resolved-service"
    assert eval_count == 1  # cached
    
    # 3. Transient Scope
    transient_count = 0
    def transient_factory():
        nonlocal transient_count
        transient_count += 1
        class Transient:
            pass
        return Transient()
        
    container.register_transient("transient_svc", transient_factory)
    t1 = container.get("transient_svc")
    t2 = container.get("transient_svc")
    assert t1 is not t2
    assert transient_count == 2
    
    # 4. Parameterized Factory Scope
    def param_factory(x: int, y: int):
        return x + y
        
    container.register_factory("add_svc", param_factory)
    res_val = container.get("add_svc", 3, y=7)
    assert res_val == 10

@pytest.mark.anyio
async def test_check_service_health():
    # 1. No health method
    h1 = check_service_health("svc1", object())
    assert h1.status == HealthStatus.HEALTHY
    assert "operational" in h1.message
    
    # 2. String health status
    h2 = check_service_health("svc2", MockHealthService("WARNING"))
    assert h2.status == HealthStatus.WARNING
    
    # 3. Dict health status
    h3 = check_service_health("svc3", MockHealthService({"status": "ERROR", "message": "out of memory", "details": {"core": 0}}))
    assert h3.status == HealthStatus.ERROR
    assert h3.message == "out of memory"
    assert h3.details == {"core": 0}
    
    # 4. SubsystemHealth instance
    sub_h = SubsystemHealth(name="test", status=HealthStatus.WARNING, message="sub_msg")
    h4 = check_service_health("svc4", MockHealthService(sub_h))
    assert h4.status == HealthStatus.WARNING
    assert h4.message == "sub_msg"
    
    # 5. Async health method
    h5 = check_service_health("svc5", MockHealthService("HEALTHY", is_async=True))
    assert h5.status == HealthStatus.WARNING
    assert "asynchronous" in h5.message
    
    # 6. Exception in health method
    class MockServiceWithCrash:
        def health(self):
            raise RuntimeError("crash")
    mock_svc = MockServiceWithCrash()
    h6 = check_service_health("svc6", mock_svc)
    assert h6.status == HealthStatus.ERROR
    assert "diagnostic check failed" in h6.message

@pytest.mark.anyio
async def test_kernel_config():
    config = OrionKernelConfig.load_defaults()
    assert config.paths.workspace_root == "/home/warlock/ORION"
    assert config.models.default_llm == "gemini-1.5-pro"

@pytest.mark.anyio
async def test_kernel_boot_shutdown_restart():
    OrionKernel.reset_instance()
    kernel = OrionKernel.get_instance()
    
    # Verify initial state
    assert kernel.state() == KernelState.STOPPED
    ctx = kernel.context()
    assert ctx.state == KernelState.STOPPED
    
    # Subscribe to boot events
    boot_events = []
    def on_event(event: OrionEvent):
        boot_events.append(event)
        
    kernel.subscribe("KernelBooting", on_event)
    kernel.subscribe("KernelReady", on_event)
    kernel.subscribe("KernelShutdown", on_event)
    kernel.subscribe("KernelRestart", on_event)
    
    # Boot the kernel
    await kernel.boot()
    assert kernel.state() == KernelState.READY
    assert kernel.context().state == KernelState.READY
    
    # Check loaded services
    loaded = kernel.list_services()
    expected = [
        "event_bus", "memory_engine", "knowledge_engine", "planner",
        "desktop_controller", "mission_engine", "workflow_engine",
        "scheduler", "telemetry", "llm_router"
    ]
    for exp in expected:
        assert exp in loaded
        
    # Check that events were fired
    assert any(isinstance(e, KernelBooting) for e in boot_events)
    assert any(isinstance(e, KernelReady) for e in boot_events)
    
    # Verify health aggregation
    h = kernel.health()
    assert h.kernel_status == HealthStatus.HEALTHY
    assert h.planner.status == HealthStatus.HEALTHY
    assert h.knowledge.status == HealthStatus.HEALTHY
    assert h.memory.status == HealthStatus.HEALTHY
    assert h.desktop.status == HealthStatus.HEALTHY
    assert h.mission.status == HealthStatus.HEALTHY
    
    # Inject a failing service and verify health updates
    kernel.register_service("planner", MockHealthService("ERROR"))
    h2 = kernel.health()
    assert h2.planner.status == HealthStatus.ERROR
    assert h2.kernel_status == HealthStatus.ERROR
    
    # Test restart
    await kernel.restart()
    assert kernel.state() == KernelState.READY
    assert any(isinstance(e, KernelRestart) for e in boot_events)
    
    # Test shutdown
    scheduler_mock = MockStoppingService()
    kernel.register_service("scheduler", scheduler_mock)
    
    await kernel.shutdown()
    assert kernel.state() == KernelState.STOPPED
    assert scheduler_mock.stop_called == 1
    assert len(kernel.list_services()) == 0
    assert any(isinstance(e, KernelShutdown) for e in boot_events)
    
    # Double boot/shutdown safety
    # Boot should be fine
    await kernel.boot()
    # Booting again should log warning and return early
    await kernel.boot()
    assert kernel.state() == KernelState.READY
    
    # Shutdown again should return early
    await kernel.shutdown()
    await kernel.shutdown()
    assert kernel.state() == KernelState.STOPPED

@pytest.mark.anyio
async def test_kernel_boot_failure():
    # Force a boot failure by overriding registry/boot manager
    OrionKernel.reset_instance()
    config = OrionKernelConfig()
    config.paths.persist_dir = "/nonexistent/path/for/failure"
    kernel = OrionKernel.get_instance(config)
    
    # Since VectorDB falls back to SimpleVectorDB, it won't crash on bad path.
    # Let's mock boot_manager to raise an exception.
    async def mock_run_boot(cfg):
        raise RuntimeError("simulated startup crash")
        
    kernel._boot_manager.run_boot_sequence = mock_run_boot
    
    errors = []
    kernel.subscribe("KernelError", lambda e: errors.append(e))
    
    with pytest.raises(RuntimeError, match="simulated startup crash"):
        await kernel.boot()
        
    assert kernel.state() == KernelState.ERROR
    assert len(errors) == 1
    assert isinstance(errors[0], KernelError)
    assert errors[0].data["error"] == "simulated startup crash"
    OrionKernel.reset_instance()
