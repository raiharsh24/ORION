from typing import Dict, Any, List, Optional, Callable
import inspect
from loguru import logger

from app.kernel.state import KernelState
from app.kernel.config import OrionKernelConfig
from app.kernel.context import OrionKernelContext, UserContext, MissionContext, WorkspaceContext, SystemMetadata
from app.kernel.health import KernelHealth, check_service_health, HealthStatus, SubsystemHealth
from app.kernel.registry import OrionServiceRegistry
from app.kernel.boot import BootManager
from app.kernel.lifecycle import (
    KernelBooting, KernelReady, KernelBusy, KernelShutdown,
    KernelRestart, KernelError, ServiceRegistered, ServiceStarted,
    ServiceStopped, ServiceFailed
)
from app.events.events import OrionEvent

class OrionKernel:
    """
    Central System Kernel coordinating all subsystems, lifecycle states, events, 
    registries, contexts, and configurations in ORION.
    """
    _instance: Optional['OrionKernel'] = None

    def __init__(self, config: Optional[OrionKernelConfig] = None) -> None:
        """Initialize the OrionKernel."""
        self._config = config or OrionKernelConfig()
        self._state = KernelState.STOPPED
        self._registry = OrionServiceRegistry()
        self._boot_manager = BootManager(self._registry)
        self._context: Optional[OrionKernelContext] = None
        self._local_subscribers: Dict[str, List[Callable[[OrionEvent], Any]]] = {}

    @classmethod
    def get_instance(cls, config: Optional[OrionKernelConfig] = None) -> 'OrionKernel':
        """Retrieve the global Kernel singleton instance."""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets the singleton instance."""
        cls._instance = None

    async def boot(self) -> None:
        """
        Triggers the BootManager startup timeline.
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
            self._context = await self._boot_manager.run_boot_sequence(self._config)
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
        
        # Stop scheduler/services if they expose stop/shutdown hooks
        scheduler = self.get_service("scheduler")
        if scheduler and hasattr(scheduler, "stop"):
            try:
                if inspect.iscoroutinefunction(scheduler.stop):
                    await scheduler.stop()
                else:
                    scheduler.stop()
            except Exception as e:
                logger.error(f"Error stopping scheduler during shutdown: {str(e)}")
                
        # Unregister all services
        services = self.list_services()
        for name in services:
            self.unregister_service(name)
            
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
        Registers a dependency in the registry.

        Args:
            name (str): Service name.
            service (Any): Service instance or factory callable.
            lazy (bool): If True, instantiates on first access.
        """
        self._registry.register(name, service, lazy=lazy)
        
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

        Args:
            name (str): Service name.
        """
        self._registry.unregister(name)
        
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

        Args:
            name (str): Service name.

        Returns:
            Optional[Any]: Registered service.
        """
        return self._registry.get(name)

    def list_services(self) -> List[str]:
        """
        Lists all registered service names.

        Returns:
            List[str]: Service name identifiers.
        """
        return self._registry.list_services()

    def health(self) -> KernelHealth:
        """
        Retrieves the consolidated health state of the entire system.

        Returns:
            KernelHealth: Consolidated health status.
        """
        planner_svc = self.get_service("planner")
        knowledge_svc = self.get_service("knowledge_engine")
        memory_svc = self.get_service("memory_engine")
        desktop_svc = self.get_service("desktop_controller")
        mission_svc = self.get_service("mission_engine")
        workflow_svc = self.get_service("workflow_engine")
        scheduler_svc = self.get_service("scheduler")
        llm_svc = self.get_service("llm_router")
        
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
        
        statuses = [p_health.status, k_health.status, memory_health.status, d_health.status, mi_health.status]
        if HealthStatus.ERROR in statuses or self._state == KernelState.ERROR:
            overall = HealthStatus.ERROR
        elif HealthStatus.WARNING in statuses:
            overall = HealthStatus.WARNING
        elif self._state == KernelState.STOPPED:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.HEALTHY
            
        return KernelHealth(
            kernel_status=overall,
            planner=p_health,
            knowledge=k_health,
            memory=memory_health,
            desktop=d_health,
            mission=mi_health,
            workflow=w_health,
            scheduler=s_health,
            llm=l_health
        )

    def state(self) -> KernelState:
        """
        Retrieves the current runtime state of the Kernel.

        Returns:
            KernelState: Current status.
        """
        return self._state

    def context(self) -> OrionKernelContext:
        """
        Retrieves the global context object.

        Returns:
            OrionKernelContext: Context state mapping.
        """
        if self._context is None:
            user_ctx = UserContext()
            mission_ctx = MissionContext()
            workspace_ctx = WorkspaceContext(active_workspace_path=self._config.paths.workspace_root)
            metadata = SystemMetadata()
            self._context = OrionKernelContext(
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

    async def publish(self, event: OrionEvent) -> None:
        """
        Broadcasts an event to the EventBus gateway.

        Args:
            event (OrionEvent): Target event.
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

    def subscribe(self, event_type: str, callback: Callable[[OrionEvent], Any]) -> None:
        """
        Registers a subscriber callback in the EventBus topic.

        Args:
            event_type (str): Event topic.
            callback (Callable): Callback executor.
        """
        if event_type not in self._local_subscribers:
            self._local_subscribers[event_type] = []
        self._local_subscribers[event_type].append(callback)
        
        event_bus = self.get_service("event_bus")
        if event_bus:
            event_bus.subscribe(event_type, callback)
