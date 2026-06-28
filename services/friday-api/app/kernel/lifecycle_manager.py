import inspect
from typing import Dict, List, Any, Optional
from loguru import logger
from app.kernel.module import FridayModuleRegistry

class FridayLifecycleManager:
    """
    Orchestrates sequential transitions (initialize, start, pause, resume, shutdown)
    for all registered subsystem modules based on topological dependency graphing.
    """
    def __init__(self, module_registry: FridayModuleRegistry) -> None:
        self._registry = module_registry
        self._states: Dict[str, str] = {}

    async def initialize_all(self) -> None:
        """Initializes modules in forward dependency order."""
        order = self._registry.topological_sort()
        logger.info(f"Initializing modules: {order}")
        for name in order:
            module = self._registry.get_module(name)
            if not module:
                continue

            self._states[name] = "initializing"
            init_hook = getattr(module, "initialize", getattr(module, "init", None))

            if init_hook and callable(init_hook):
                try:
                    # Verify signature expects zero arguments
                    sig = inspect.signature(init_hook)
                    req_params = [
                        p for p in sig.parameters.values()
                        if p.default == inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    ]
                    if len(req_params) == 0:
                        if inspect.iscoroutinefunction(init_hook):
                            await init_hook()
                        else:
                            init_hook()
                        logger.debug(f"Module '{name}' initialization - SUCCESS")
                    else:
                        logger.debug(f"Module '{name}' init skipped - requires arguments")
                except Exception as e:
                    self._states[name] = "error"
                    logger.error(f"Module '{name}' initialization - FAILED: {str(e)}")
                    raise e
            self._states[name] = "initialized"

    async def start_all(self) -> None:
        """Starts all initialized modules in forward dependency order."""
        order = self._registry.topological_sort()
        logger.info(f"Starting modules: {order}")
        for name in order:
            current_state = self._states.get(name, "uninitialized")
            if current_state == "uninitialized" or current_state == "initializing":
                logger.warning(f"Module '{name}' was not initialized prior to starting. Running lazy initialization.")
                module = self._registry.get_module(name)
                init_hook = getattr(module, "initialize", getattr(module, "init", None))
                if init_hook and callable(init_hook):
                    if inspect.iscoroutinefunction(init_hook):
                        await init_hook()
                    else:
                        init_hook()
                self._states[name] = "initialized"

            module = self._registry.get_module(name)
            if not module:
                continue

            self._states[name] = "starting"
            start_hook = getattr(module, "start", None)

            if start_hook and callable(start_hook):
                try:
                    # Verify signature expects zero arguments
                    sig = inspect.signature(start_hook)
                    req_params = [
                        p for p in sig.parameters.values()
                        if p.default == inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    ]
                    if len(req_params) == 0:
                        if inspect.iscoroutinefunction(start_hook):
                            await start_hook()
                        else:
                            start_hook()
                        logger.debug(f"Module '{name}' startup - SUCCESS")
                    else:
                        logger.debug(f"Module '{name}' startup skipped - requires arguments")
                except Exception as e:
                    self._states[name] = "error"
                    logger.error(f"Module '{name}' startup - FAILED: {str(e)}")
                    raise e
            self._states[name] = "started"

    async def shutdown_all(self) -> None:
        """Gracefully shuts down modules in REVERSE dependency order."""
        order = list(reversed(self._registry.topological_sort()))
        logger.info(f"Shutting down modules in reverse order: {order}")
        for name in order:
            module = self._registry.get_module(name)
            if not module:
                continue

            self._states[name] = "stopping"
            shutdown_hook = getattr(module, "shutdown", getattr(module, "stop", getattr(module, "close", None)))

            if shutdown_hook and callable(shutdown_hook):
                try:
                    # Verify signature expects zero arguments
                    sig = inspect.signature(shutdown_hook)
                    req_params = [
                        p for p in sig.parameters.values()
                        if p.default == inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    ]
                    if len(req_params) == 0:
                        if inspect.iscoroutinefunction(shutdown_hook):
                            await shutdown_hook()
                        else:
                            shutdown_hook()
                        logger.debug(f"Module '{name}' shutdown - SUCCESS")
                    else:
                        logger.debug(f"Module '{name}' shutdown skipped - requires arguments")
                except Exception as e:
                    self._states[name] = "error"
                    logger.error(f"Module '{name}' shutdown - FAILED: {str(e)}")
            self._states[name] = "stopped"

    async def pause_all(self) -> None:
        """Pauses modules in reverse dependency order."""
        order = list(reversed(self._registry.topological_sort()))
        for name in order:
            if self._states.get(name) == "started":
                module = self._registry.get_module(name)
                pause_hook = getattr(module, "pause", None)
                if pause_hook and callable(pause_hook):
                    try:
                        if inspect.iscoroutinefunction(pause_hook):
                            await pause_hook()
                        else:
                            pause_hook()
                        self._states[name] = "paused"
                    except Exception as e:
                        logger.error(f"Module '{name}' pause failed: {str(e)}")

    async def resume_all(self) -> None:
        """Resumes paused modules in forward dependency order."""
        order = self._registry.topological_sort()
        for name in order:
            if self._states.get(name) == "paused":
                module = self._registry.get_module(name)
                resume_hook = getattr(module, "resume", None)
                if resume_hook and callable(resume_hook):
                    try:
                        if inspect.iscoroutinefunction(resume_hook):
                            await resume_hook()
                        else:
                            resume_hook()
                        self._states[name] = "started"
                    except Exception as e:
                        logger.error(f"Module '{name}' resume failed: {str(e)}")

    def get_state(self, name: str) -> str:
        """Returns the lifecycle state of a specific module."""
        return self._states.get(name, "unregistered")
