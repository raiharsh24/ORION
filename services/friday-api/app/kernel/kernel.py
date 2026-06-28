from typing import Dict, Any, List, Optional, Callable
import inspect
from loguru import logger

from app.kernel.state import KernelState
from app.kernel.config import FridayKernelConfig
from app.kernel.context import FridayKernelContext, UserContext, MissionContext, WorkspaceContext, SystemMetadata
from app.kernel.health import KernelHealth, check_service_health, HealthStatus, SubsystemHealth
from app.kernel.boot import BootManager
from app.kernel.lifecycle import (
    KernelBooting, KernelReady, KernelBusy, KernelShutdown,
    KernelRestart, KernelError, ServiceRegistered, ServiceStarted,
    ServiceStopped, ServiceFailed
)
from app.events.events import FridayEvent

# Alpha 4.0 Core Runtime Imports
from app.kernel.container import FridayServiceContainer
from app.kernel.module import FridayModuleRegistry
from app.kernel.capability import FridayCapabilityRegistry
from app.kernel.lifecycle_manager import FridayLifecycleManager
from app.kernel.config_system import FridayConfigSystem
from app.kernel.health_monitor import FridayHealthMonitor

class FridayKernel:
    """
    Central System Kernel coordinating all subsystems, lifecycle states, events, 
    registries, contexts, and configurations in FRIDAY.
    """
    _instance: Optional['FridayKernel'] = None

    def __init__(self, config: Optional[FridayKernelConfig] = None) -> None:
        """Initialize the FridayKernel."""
        # 1. Config System
        self._config_system = FridayConfigSystem(config or FridayKernelConfig())
        self._config = self._config_system.get_config()
        self._state = KernelState.STOPPED
        
        # 2. Dependency Container
        self._container = FridayServiceContainer()
        self._registry = self._container  # Backward compatibility mapping
        
        # 3. Module & Capability Registries
        self._module_registry = FridayModuleRegistry()
        self._capability_registry = FridayCapabilityRegistry()
        
        # 4. Lifecycle & Health Monitoring
        self._lifecycle_manager = FridayLifecycleManager(self._module_registry)
        self._health_monitor = FridayHealthMonitor()
        
        # 5. Core context & subscribers
        self._boot_manager = BootManager(self._container)
        self._context: Optional[FridayKernelContext] = None
        self._local_subscribers: Dict[str, List[Callable[[FridayEvent], Any]]] = {}

    @classmethod
    def get_instance(cls, config: Optional[FridayKernelConfig] = None) -> 'FridayKernel':
        """Retrieve the global Kernel singleton instance."""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets the singleton instance."""
        cls._instance = None

    @property
    def config_system(self) -> FridayConfigSystem:
        return self._config_system

    @property
    def container(self) -> FridayServiceContainer:
        return self._container

    @property
    def module_registry(self) -> FridayModuleRegistry:
        return self._module_registry

    @property
    def capability_registry(self) -> FridayCapabilityRegistry:
        return self._capability_registry

    @property
    def lifecycle_manager(self) -> FridayLifecycleManager:
        return self._lifecycle_manager

    @property
    def health_monitor(self) -> FridayHealthMonitor:
        return self._health_monitor

    async def boot(self) -> None:
        """
        Triggers the BootManager startup timeline and runs module lifecycles.
        """
        if self._state != KernelState.STOPPED and self._state != KernelState.ERROR:
            logger.warning(f"Kernel is already booted or booting. Current state: {self._state}")
            return
            
        logger.info("Kernel boot sequence initiated.")
        self._state = KernelState.BOOTING
        
        # Create and dispatch KernelBooting event
        booting_event = KernelBooting()
        await self.publish(booting_event)
        
        self._state = KernelState.INITIALIZING
        
        try:
            # 1. Run Boot sequence mapping modules & DI Container registrations
            self._context = await self._boot_manager.run_boot_sequence(self._config)
            
            # 2. Transition all module lifecycles
            logger.info("Initializing and starting registered modules...")
            await self._lifecycle_manager.initialize_all()
            await self._lifecycle_manager.start_all()

            self._state = KernelState.READY
            self._context.state = KernelState.READY
            
            # Dispatch KernelReady event
            ready_event = KernelReady()
            await self.publish(ready_event)
            logger.info("Kernel successfully booted and ready.")
        except Exception as e:
            self._state = KernelState.ERROR
            logger.error(f"Kernel boot failed: {str(e)}")
            # Dispatch KernelError event
            error_event = KernelError(error_message=str(e))
            await self.publish(error_event)
            raise e

    async def shutdown(self) -> None:
        """
        Teardown all registered services gracefully.
        """
        if self._state == KernelState.STOPPED:
            logger.info("Kernel is already stopped.")
            return
            
        logger.info("Kernel shutdown sequence initiated.")
        self._state = KernelState.SHUTTING_DOWN
        if self._context:
            self._context.state = KernelState.SHUTTING_DOWN
            
        # Dispatch KernelShutdown event
        shutdown_event = KernelShutdown(reason="Graceful system shutdown")
        await self.publish(shutdown_event)
        
        # Shutdown all modules using topological reverse order
        try:
            await self._lifecycle_manager.shutdown_all()
        except Exception as e:
            logger.error(f"Error during lifecycle shutdown: {str(e)}")

        for name in list(self._container.list_services()):
            self._container.unregister(name)
        self._state = KernelState.STOPPED
        if self._context:
            self._context.state = KernelState.STOPPED
        logger.info("Kernel shutdown complete.")

    async def restart(self) -> None:
        """
        Trigger system reboot sequence.
        """
        logger.info("Kernel reboot sequence initiated.")
        restart_event = KernelRestart()
        await self.publish(restart_event)
        
        await self.shutdown()
        await self.boot()

    def register_service(self, name: str, service: Any, lazy: bool = False) -> None:
        """
        Registers a dependency in the container registry (Backward compatibility wrapper).
        """
        self._container.register(name, service, lazy=lazy)
        
        # Register in the module registry as well to support lifecycle transitions
        self._module_registry.register_module(
            name=name,
            version="1.0.0",
            dependencies=[],
            instance_or_factory=service,
            lazy=lazy
        )
        
        # Flush local callbacks to new event bus if event bus was just registered
        if name == "event_bus":
            for event_type, callbacks in self._local_subscribers.items():
                for cb in callbacks:
                    service.subscribe(event_type, cb)
                    
        # Publish ServiceRegistered event
        try:
            class_name = service.__class__.__name__ if not callable(service) else "factory"
            event = ServiceRegistered(service_name=name, service_class=class_name)
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self.publish(event))
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug(f"Could not publish ServiceRegistered event: {str(e)}")

    def unregister_service(self, name: str) -> None:
        """
        Deregisters a service from registry.
        """
        self._container.unregister(name)
        
        # Publish ServiceStopped event
        try:
            event = ServiceStopped(service_name=name)
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self.publish(event))
            except RuntimeError:
                pass
        except Exception as e:
            logger.debug(f"Could not publish ServiceStopped event: {str(e)}")

    def get_service(self, name: str) -> Optional[Any]:
        """
        Resolves a service from container registry.
        """
        try:
            return self._container.get(name)
        except KeyError:
            return None

    def list_services(self) -> List[str]:
        """
        Lists all registered service names.
        """
        return self._container.list_services()

    def health(self) -> KernelHealth:
        """
        Consolidates the active health checks of the registered subsystems,
        falling back to default checks for backward compatibility.
        """
        planner_svc = self.get_service("planner")
        knowledge_svc = self.get_service("knowledge_engine")
        memory_svc = self.get_service("memory_engine")
        desktop_svc = self.get_service("desktop_controller")
        mission_svc = self.get_service("mission_engine")
        workflow_svc = self.get_service("workflow_engine")
        scheduler_svc = self.get_service("scheduler")
        llm_svc = self.get_service("llm_router")
        agents_svc = self.get_service("agent_coordinator")
        runtime_svc = self.get_service("runtime_scheduler_bridge")
        
        p_health = check_service_health("planner", planner_svc) if planner_svc else SubsystemHealth(name="planner", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        k_health = check_service_health("knowledge", knowledge_svc) if knowledge_svc else SubsystemHealth(name="knowledge", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        memory_health = check_service_health("memory", memory_svc) if memory_svc else SubsystemHealth(name="memory", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        d_health = check_service_health("desktop", desktop_svc) if desktop_svc else SubsystemHealth(name="desktop", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        automation_svc = self.get_service("desktop_automation")
        if automation_svc:
            auto_health = check_service_health("desktop_automation", automation_svc)
            if auto_health.status == HealthStatus.ERROR:
                d_health.status = HealthStatus.ERROR
            elif auto_health.status == HealthStatus.WARNING and d_health.status != HealthStatus.ERROR:
                d_health.status = HealthStatus.WARNING
            if auto_health.message:
                d_health.message = f"{d_health.message} | Automation: {auto_health.message}"
        mi_health = check_service_health("mission", mission_svc) if mission_svc else SubsystemHealth(name="mission", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        w_health = check_service_health("workflow", workflow_svc) if workflow_svc else SubsystemHealth(name="workflow", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        s_health = check_service_health("scheduler", scheduler_svc) if scheduler_svc else SubsystemHealth(name="scheduler", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        l_health = check_service_health("llm", llm_svc) if llm_svc else SubsystemHealth(name="llm", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        a_health = check_service_health("agents", agents_svc) if agents_svc else SubsystemHealth(name="agents", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        r_health = check_service_health("workflow_runtime", runtime_svc) if runtime_svc else SubsystemHealth(name="workflow_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        
        statuses = [p_health.status, k_health.status, memory_health.status, d_health.status, mi_health.status, a_health.status, r_health.status]
        if HealthStatus.ERROR in statuses or self._state == KernelState.ERROR:
            overall = HealthStatus.ERROR
        elif HealthStatus.WARNING in statuses:
            overall = HealthStatus.WARNING
        elif self._state == KernelState.STOPPED:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.HEALTHY

        # Populate the dynamic health monitor
        self._health_monitor.report_health("planner", p_health.status, p_health.message)
        self._health_monitor.report_health("knowledge", k_health.status, k_health.message)
        self._health_monitor.report_health("memory", memory_health.status, memory_health.message)
        self._health_monitor.report_health("desktop", d_health.status, d_health.message)
        self._health_monitor.report_health("mission", mi_health.status, mi_health.message)
        self._health_monitor.report_health("workflow", w_health.status, w_health.message)
        self._health_monitor.report_health("scheduler", s_health.status, s_health.message)
        self._health_monitor.report_health("llm", l_health.status, l_health.message)
        self._health_monitor.report_health("agents", a_health.status, a_health.message)
        self._health_monitor.report_health("workflow_runtime", r_health.status, r_health.message)
            
        return KernelHealth(
            kernel_status=overall,
            planner=p_health,
            knowledge=k_health,
            memory=memory_health,
            desktop=d_health,
            mission=mi_health,
            workflow=w_health,
            scheduler=s_health,
            llm=l_health,
            agents=a_health,
            workflow_runtime=r_health,
        )

    def state(self) -> KernelState:
        """
        Retrieves the current runtime state of the Kernel.
        """
        return self._state

    def context(self) -> FridayKernelContext:
        """
        Retrieves the global context object.
        """
        if self._context is None:
            user_ctx = UserContext()
            mission_ctx = MissionContext()
            workspace_ctx = WorkspaceContext(active_workspace_path=self._config.paths.workspace_root)
            metadata = SystemMetadata()
            self._context = FridayKernelContext(
                user=user_ctx,
                mission=mission_ctx,
                workspace=workspace_ctx,
                loaded_services=self.list_services(),
                state=self._state,
                config=self._config,
                metadata=metadata
            )
        else:
            self._context.loaded_services = self.list_services()
            self._context.state = self._state
        return self._context

    async def publish(self, event: FridayEvent) -> None:
        """
        Broadcasts an event to the EventBus gateway.
        """
        event_bus = self.get_service("event_bus")
        if event_bus:
            await event_bus.publish(event)
            
        if event.topic in self._local_subscribers:
            for cb in self._local_subscribers[event.topic]:
                try:
                    if inspect.iscoroutinefunction(cb):
                        await cb(event)
                    else:
                        cb(event)
                except Exception as e:
                    logger.error(f"Error in local subscriber callback for topic {event.topic}: {str(e)}")

    def subscribe(self, event_type: str, callback: Callable[[FridayEvent], Any]) -> None:
        """
        Registers a subscriber callback in the EventBus topic.
        """
        if event_type not in self._local_subscribers:
            self._local_subscribers[event_type] = []
        self._local_subscribers[event_type].append(callback)
        
        event_bus = self.get_service("event_bus")
        if event_bus:
            event_bus.subscribe(event_type, callback)
