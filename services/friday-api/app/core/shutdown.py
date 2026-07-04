import asyncio
from typing import Set
from loguru import logger

from app.events.bus import EventBus
from app.kernel.logging_telemetry import FridayTelemetryLogger

_active_websockets: Set[asyncio.Task] = set()
_ws_lock = asyncio.Lock()


async def track_websocket(task: asyncio.Task) -> None:
    async with _ws_lock:
        _active_websockets.add(task)
    task.add_done_callback(_remove_websocket)


def _remove_websocket(task: asyncio.Task) -> None:
    try:
        _active_websockets.discard(task)
    except RuntimeError:
        pass


async def close_all_websockets(timeout: float = 5.0) -> int:
    async with _ws_lock:
        tasks = list(_active_websockets)
        _active_websockets.clear()

    if not tasks:
        return 0

    logger.info(f"Closing {len(tasks)} active WebSocket connections...")
    for t in tasks:
        t.cancel()

    done, pending = await asyncio.wait(tasks, timeout=timeout)
    for t in pending:
        t.cancel()
        try:
            await asyncio.wait_for(t, timeout=1.0)
        except (asyncio.CancelledError, Exception):
            pass

    return len(tasks)


async def shutdown_plugin_runtime(kernel) -> None:
    plugin_runtime = kernel.get_service("plugin_runtime")
    if plugin_runtime and hasattr(plugin_runtime, "shutdown"):
        try:
            await asyncio.wait_for(plugin_runtime.shutdown(), timeout=10.0)
            logger.info("Plugin runtime shut down")
        except asyncio.TimeoutError:
            logger.warning("Plugin runtime shutdown timed out")


async def shutdown_event_bus(event_bus: EventBus) -> None:
    if event_bus and hasattr(event_bus, "shutdown"):
        try:
            await asyncio.wait_for(event_bus.shutdown(), timeout=5.0)
            logger.info("Event bus shut down")
        except asyncio.TimeoutError:
            logger.warning("Event bus shutdown timed out")


async def flush_memory_stores(kernel) -> None:
    memory_engine = kernel.get_service("memory_engine")
    if memory_engine and hasattr(memory_engine, "shutdown"):
        try:
            await asyncio.wait_for(memory_engine.shutdown(), timeout=5.0)
            logger.info("Memory engine flushed")
        except asyncio.TimeoutError:
            logger.warning("Memory engine shutdown timed out")


async def graceful_shutdown(kernel, event_bus: EventBus, timeout: float = 30.0) -> None:
    logger.info("=== GRACEFUL SHUTDOWN STARTED ===")

    try:
        await asyncio.wait_for(asyncio.gather(
            close_all_websockets(timeout=5.0),
            shutdown_plugin_runtime(kernel),
            flush_memory_stores(kernel),
        ), timeout=timeout)

        await shutdown_event_bus(event_bus)

        # Publish shutdown event
        if event_bus:
            from app.kernel.lifecycle import KernelShutdown
            try:
                await asyncio.wait_for(
                    event_bus.publish(KernelShutdown(reason="Graceful shutdown")),
                    timeout=5.0,
                )
            except (asyncio.TimeoutError, Exception):
                pass

    except asyncio.TimeoutError:
        logger.warning("Graceful shutdown timed out, forcing remaining cleanup")

    logger.info("=== GRACEFUL SHUTDOWN COMPLETE ===")
