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
        self._config_system = FridayConfigSystem(config)
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
        from app.kernel.uptime import KernelUptime
        KernelUptime.start()
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
        runtime_svc = self.get_service("workflow_runtime_manager")
        
        intent_analyzer_svc = self.get_service("intent_analyzer")
        strategy_manager_svc = self.get_service("strategy_manager")
        extractor_registry_svc = self.get_service("extractor_registry")
        context_ranker_svc = self.get_service("context_ranker")
        token_allocator_svc = self.get_service("token_allocator")
        context_validator_svc = self.get_service("context_validator")
        context_compressor_svc = self.get_service("context_compressor")
        prompt_assembler_svc = self.get_service("prompt_assembler")
        pipeline_orchestrator_svc = self.get_service("pipeline_orchestrator")
        universal_tool_registry_svc = self.get_service("universal_tool_registry")
        tool_selection_engine_svc = self.get_service("tool_selection_engine")
        tool_execution_engine_svc = self.get_service("tool_execution_engine")
        workflow_engine_v2_svc = self.get_service("workflow_engine_v2")
        mission_engine_v2_svc = self.get_service("mission_engine_v2")
        capability_registry_v2_svc = self.get_service("capability_registry_v2")
        capability_resolver_svc = self.get_service("capability_resolver")
        plugin_runtime_svc = self.get_service("plugin_runtime")
        package_manager_svc = self.get_service("package_manager")
        plugin_security_svc = self.get_service("plugin_security")
        agent_framework_svc = self.get_service("agent_manager")
        blackboard_svc = self.get_service("blackboard")
        coordinator_svc = self.get_service("coordinator")
        delegation_mgr_svc = self.get_service("delegation_manager")
        persistence_mgr_svc = self.get_service("persistence_manager")
        recovery_mgr_svc = self.get_service("recovery_manager")
        metrics_svc = self.get_service("metrics_collector")
        planning_svc = self.get_service("planning_engine")
        mission_runtime_svc = self.get_service("mission_runtime")
        
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
        plugin_reg_svc = self.get_service("plugin_registry")
        plugin_reg_health = check_service_health("plugin_registry", plugin_reg_svc) if plugin_reg_svc else SubsystemHealth(name="plugin_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        plugin_loader_svc = self.get_service("plugin_loader")
        plugin_loader_health = check_service_health("plugin_loader", plugin_loader_svc) if plugin_loader_svc else SubsystemHealth(name="plugin_loader", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        
        ia_health = check_service_health("intent_analyzer", intent_analyzer_svc) if intent_analyzer_svc else SubsystemHealth(name="intent_analyzer", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        sm_health = check_service_health("strategy_manager", strategy_manager_svc) if strategy_manager_svc else SubsystemHealth(name="strategy_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        er_health = check_service_health("extractor_registry", extractor_registry_svc) if extractor_registry_svc else SubsystemHealth(name="extractor_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        cr_health = check_service_health("context_ranker", context_ranker_svc) if context_ranker_svc else SubsystemHealth(name="context_ranker", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        ta_health = check_service_health("token_allocator", token_allocator_svc) if token_allocator_svc else SubsystemHealth(name="token_allocator", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        cv_health = check_service_health("context_validator", context_validator_svc) if context_validator_svc else SubsystemHealth(name="context_validator", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        cc_health = check_service_health("context_compressor", context_compressor_svc) if context_compressor_svc else SubsystemHealth(name="context_compressor", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        pa_health = check_service_health("prompt_assembler", prompt_assembler_svc) if prompt_assembler_svc else SubsystemHealth(name="prompt_assembler", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        po_health = check_service_health("pipeline_orchestrator", pipeline_orchestrator_svc) if pipeline_orchestrator_svc else SubsystemHealth(name="pipeline_orchestrator", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        utr_health = check_service_health("universal_tool_registry", universal_tool_registry_svc) if universal_tool_registry_svc else SubsystemHealth(name="universal_tool_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        tse_health = check_service_health("tool_selection_engine", tool_selection_engine_svc) if tool_selection_engine_svc else SubsystemHealth(name="tool_selection_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        tee_health = check_service_health("tool_execution_engine", tool_execution_engine_svc) if tool_execution_engine_svc else SubsystemHealth(name="tool_execution_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        we_health = check_service_health("workflow_engine_v2", workflow_engine_v2_svc) if workflow_engine_v2_svc else SubsystemHealth(name="workflow_engine_v2", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        me_health = check_service_health("mission_engine_v2", mission_engine_v2_svc) if mission_engine_v2_svc else SubsystemHealth(name="mission_engine_v2", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        cr2_health = check_service_health("capability_registry", capability_registry_v2_svc) if capability_registry_v2_svc else SubsystemHealth(name="capability_registry", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        cres_health = check_service_health("capability_resolver", capability_resolver_svc) if capability_resolver_svc else SubsystemHealth(name="capability_resolver", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        pr_health = check_service_health("plugin_runtime", plugin_runtime_svc) if plugin_runtime_svc else SubsystemHealth(name="plugin_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        pm_health = check_service_health("package_manager", package_manager_svc) if package_manager_svc else SubsystemHealth(name="plugin_marketplace", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        ps_health = check_service_health("plugin_security", plugin_security_svc) if plugin_security_svc else SubsystemHealth(name="plugin_security", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        af_health = check_service_health("agent_framework", agent_framework_svc) if agent_framework_svc else SubsystemHealth(name="agent_framework", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        b_health = check_service_health("blackboard", blackboard_svc) if blackboard_svc else SubsystemHealth(name="blackboard", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        c_health = check_service_health("coordinator", coordinator_svc) if coordinator_svc else SubsystemHealth(name="coordinator", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        d_health2 = check_service_health("delegation_manager", delegation_mgr_svc) if delegation_mgr_svc else SubsystemHealth(name="delegation_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        p_health2 = check_service_health("persistence_manager", persistence_mgr_svc) if persistence_mgr_svc else SubsystemHealth(name="persistence_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        r_health2 = check_service_health("recovery_manager", recovery_mgr_svc) if recovery_mgr_svc else SubsystemHealth(name="recovery_manager", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        m_health = check_service_health("metrics_collector", metrics_svc) if metrics_svc else SubsystemHealth(name="metrics_collector", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        pl_health = check_service_health("planning_engine", planning_svc) if planning_svc else SubsystemHealth(name="planning_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        rt_health = check_service_health("mission_runtime", mission_runtime_svc) if mission_runtime_svc else SubsystemHealth(name="mission_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        vision_svc = self.get_service("vision_engine")
        v_health = check_service_health("vision_engine", vision_svc) if vision_svc else SubsystemHealth(name="vision_engine", status=HealthStatus.UNKNOWN, message="Subsystem not registered")
        
        statuses = [p_health.status, k_health.status, memory_health.status, d_health.status, w_health.status, mi_health.status, s_health.status, l_health.status, a_health.status, r_health.status, plugin_reg_health.status, plugin_loader_health.status, ia_health.status, sm_health.status, er_health.status, cr_health.status, ta_health.status, cv_health.status, cc_health.status, pa_health.status, po_health.status, utr_health.status, tse_health.status, tee_health.status, we_health.status, me_health.status, cr2_health.status, cres_health.status, pr_health.status, pm_health.status, ps_health.status, af_health.status, b_health.status, c_health.status, d_health2.status, p_health2.status, r_health2.status, m_health.status, pl_health.status, rt_health.status, v_health.status]
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
        self._health_monitor.report_health("plugin_registry", plugin_reg_health.status, plugin_reg_health.message)
        self._health_monitor.report_health("plugin_loader", plugin_loader_health.status, plugin_loader_health.message)
        self._health_monitor.report_health("intent_analyzer", ia_health.status, ia_health.message)
        self._health_monitor.report_health("strategy_manager", sm_health.status, sm_health.message)
        self._health_monitor.report_health("extractor_registry", er_health.status, er_health.message)
        self._health_monitor.report_health("context_ranker", cr_health.status, cr_health.message)
        self._health_monitor.report_health("token_allocator", ta_health.status, ta_health.message)
        self._health_monitor.report_health("context_validator", cv_health.status, cv_health.message)
        self._health_monitor.report_health("context_compressor", cc_health.status, cc_health.message)
        self._health_monitor.report_health("prompt_assembler", pa_health.status, pa_health.message)
        self._health_monitor.report_health("pipeline_orchestrator", po_health.status, po_health.message)
        self._health_monitor.report_health("universal_tool_registry", utr_health.status, utr_health.message)
        self._health_monitor.report_health("tool_selection_engine", tse_health.status, tse_health.message)
        self._health_monitor.report_health("tool_execution_engine", tee_health.status, tee_health.message)
        self._health_monitor.report_health("workflow_engine_v2", we_health.status, we_health.message)
        self._health_monitor.report_health("mission_engine_v2", me_health.status, me_health.message)
        self._health_monitor.report_health("capability_registry_v2", cr2_health.status, cr2_health.message)
        self._health_monitor.report_health("capability_resolver", cres_health.status, cres_health.message)
        self._health_monitor.report_health("plugin_runtime", pr_health.status, pr_health.message)
        self._health_monitor.report_health("plugin_marketplace", pm_health.status, pm_health.message)
        self._health_monitor.report_health("plugin_security", ps_health.status, ps_health.message)
        self._health_monitor.report_health("agent_framework", af_health.status, af_health.message)
        self._health_monitor.report_health("blackboard", b_health.status, b_health.message)
        self._health_monitor.report_health("coordinator", c_health.status, c_health.message)
        self._health_monitor.report_health("delegation_manager", d_health2.status, d_health2.message)
        self._health_monitor.report_health("persistence_manager", p_health2.status, p_health2.message)
        self._health_monitor.report_health("recovery_manager", r_health2.status, r_health2.message)
        self._health_monitor.report_health("metrics_collector", m_health.status, m_health.message)
        self._health_monitor.report_health("planning_engine", pl_health.status, pl_health.message)
        self._health_monitor.report_health("mission_runtime", rt_health.status, rt_health.message)
        self._health_monitor.report_health("vision_engine", v_health.status, v_health.message)
            
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
            intent_analyzer=ia_health,
            strategy_manager=sm_health,
            extractor_registry=er_health,
            context_ranker=cr_health,
            token_allocator=ta_health,
            context_validator=cv_health,
            context_compressor=cc_health,
            prompt_assembler=pa_health,
            pipeline_orchestrator=po_health,
            universal_tool_registry=utr_health,
            tool_selection_engine=tse_health,
            tool_execution_engine=tee_health,
            workflow_engine_v2=we_health,
            mission_engine_v2=me_health,
            capability_registry_v2=cr2_health,
            capability_resolver=cres_health,
            plugin_registry=plugin_reg_health,
            plugin_loader=plugin_loader_health,
            plugin_runtime=pr_health,
            plugin_marketplace=pm_health,
            plugin_security=ps_health,
            agent_framework=af_health,
            blackboard=b_health,
            coordinator=c_health,
            delegation_manager=d_health2,
            persistence_manager=p_health2,
            recovery_manager=r_health2,
            metrics_collector=m_health,
            planning_engine=pl_health,
            mission_runtime=rt_health,
            vision_engine=v_health,
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
