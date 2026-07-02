import time
import asyncio
from pathlib import Path
from typing import Optional, Any, Dict, Set, Callable, Awaitable
from loguru import logger

from app.plugin_runtime.base import PluginInstance, PluginRuntimeState, PluginRuntimeConfig
from app.plugin_runtime.events import PluginReloaded, PluginFailed
from app.plugin_runtime.loader import RuntimePluginLoader
from app.plugin_runtime.unloader import PluginUnloader
from app.plugin_runtime.monitor import PluginMonitor


class PluginReloader:
    def __init__(
        self,
        loader: RuntimePluginLoader,
        unloader: PluginUnloader,
        monitor: PluginMonitor,
        event_bus: Optional[Any] = None,
        config: Optional[PluginRuntimeConfig] = None,
    ) -> None:
        self._loader = loader
        self._unloader = unloader
        self._monitor = monitor
        self._event_bus = event_bus
        self._config = config or PluginRuntimeConfig()
        self._watched_dirs: Dict[str, Dict[str, float]] = {}
        self._watch_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._on_reload_callbacks: list = []
        self._file_hashes: Dict[str, str] = {}

    def on_reload(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self._on_reload_callbacks.append(callback)

    async def reload(self, plugin_id: str) -> Optional[PluginInstance]:
        inst = self._loader.get_instance(plugin_id)
        if inst is None:
            logger.error(f"Plugin '{plugin_id}' not found for reload")
            return None

        old_state = inst.state
        reload_count = inst.reload_count
        start = time.time()
        inst.record_state(PluginRuntimeState.RELOADING)

        try:
            preserve_meta = dict(inst.metadata) if self._config.preserve_state_on_reload else {}

            unloaded = await self._unloader.unload(inst)
            if not unloaded:
                inst.record_state(PluginRuntimeState.FAILED, "Unload failed during reload")
                self._monitor.record_crash(plugin_id, inst.name, "Unload failed during reload", "reload")
                return None

            inst.record_state(PluginRuntimeState.LOADING)
            await self._loader.initialize(plugin_id)
            await self._loader.mark_ready(plugin_id)

            inst = self._loader.get_instance(plugin_id)
            if inst is None:
                raise RuntimeError(f"Plugin '{plugin_id}' lost after reload")

            inst.reload_count = reload_count + 1
            if preserve_meta:
                inst.metadata.update(preserve_meta)

            reload_time = (time.time() - start) * 1000

            self._publish(PluginReloaded(
                plugin_id=plugin_id, name=inst.name,
                reload_count=inst.reload_count,
                reload_time_ms=reload_time,
            ))
            logger.info(f"Plugin '{plugin_id}' reloaded in {reload_time:.1f}ms (count={inst.reload_count})")

            for cb in self._on_reload_callbacks:
                try:
                    await cb(plugin_id)
                except Exception as e:
                    logger.error(f"Reload callback failed for '{plugin_id}': {e}")

            return inst

        except Exception as e:
            error = str(e)
            logger.error(f"Reload failed for plugin '{plugin_id}': {e}")
            inst = self._loader.get_instance(plugin_id)
            if inst:
                inst.last_error = error
                inst.error_count += 1
                inst.record_state(PluginRuntimeState.FAILED, error)
                self._monitor.record_crash(plugin_id, inst.name, error, "reload")
                self._publish(PluginFailed(
                    plugin_id=plugin_id, name=inst.name,
                    error=error, stage="reload",
                ))
            return None

    async def start_watching(self, plugin_dir: str) -> None:
        if plugin_dir in self._watch_tasks:
            return
        self._running = True
        task = asyncio.create_task(self._watch_loop(plugin_dir))
        self._watch_tasks[plugin_dir] = task
        logger.info(f"Watching plugin directory '{plugin_dir}' for changes")

    async def stop_watching(self, plugin_dir: Optional[str] = None) -> None:
        if plugin_dir:
            task = self._watch_tasks.pop(plugin_dir, None)
            if task:
                task.cancel()
                logger.info(f"Stopped watching '{plugin_dir}'")
        else:
            for path, task in list(self._watch_tasks.items()):
                task.cancel()
            self._watch_tasks.clear()
            logger.info("Stopped all directory watchers")
        self._running = False

    async def _watch_loop(self, plugin_dir: str) -> None:
        base = Path(plugin_dir)
        interval = self._config.watch_interval_seconds
        while self._running:
            try:
                await asyncio.sleep(interval)
                if not base.exists():
                    continue
                for entry in base.iterdir():
                    if not entry.is_dir():
                        continue
                    manifest_files = list(entry.glob("plugin.json")) + list(entry.glob("manifest.json"))
                    for mf in manifest_files:
                        if await self._check_file_changed(mf):
                            plugin_id = entry.name
                            inst = self._loader.get_instance(plugin_id)
                            if inst and inst.is_running:
                                logger.info(f"Detected change in plugin '{plugin_id}', reloading...")
                                await self.reload(plugin_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watch loop error in '{plugin_dir}': {e}")

    async def _check_file_changed(self, file_path: Path) -> bool:
        import hashlib
        try:
            content = file_path.read_bytes()
            h = hashlib.md5(content).hexdigest()
            key = str(file_path)
            if key in self._file_hashes:
                if self._file_hashes[key] != h:
                    self._file_hashes[key] = h
                    return True
            else:
                self._file_hashes[key] = h
            return False
        except Exception:
            return False

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(self._event_bus.publish(event))
                except RuntimeError:
                    pass
            except Exception:
                pass

    async def shutdown(self) -> None:
        await self.stop_watching()
