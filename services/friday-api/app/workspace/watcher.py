from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set
from loguru import logger


class ChangeType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class WorkspaceChangeEvent:
    change_type: ChangeType
    file_path: str
    project_root: str
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


ChangeHandler = Callable[[WorkspaceChangeEvent], None]


@dataclass
class WatchedDirectory:
    path: str
    file_hashes: Dict[str, float] = field(default_factory=dict)
    extensions: Set[str] = field(default_factory=lambda: {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env"})

    IGNORE_DIRS = {
        ".git", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", "dist", "build", "target", ".next",
        ".cache", ".idea", ".vscode",
    }

    def scan(self) -> List[WorkspaceChangeEvent]:
        """Scan directory and return change events since last scan."""
        events: List[WorkspaceChangeEvent] = []
        current: Dict[str, float] = {}

        if not os.path.isdir(self.path):
            for fpath in list(self.file_hashes.keys()):
                if os.path.normpath(fpath).startswith(os.path.normpath(self.path)):
                    events.append(WorkspaceChangeEvent(
                        change_type=ChangeType.DELETED,
                        file_path=fpath,
                        project_root=self.path,
                    ))
            self.file_hashes.clear()
            return events

        base_depth = self.path.count(os.sep)

        for root, dirs, files in os.walk(self.path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

            for fname in files:
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()

                if ext not in self.extensions:
                    continue
                if fname.startswith("."):
                    continue

                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue

                current[fpath] = mtime

                if fpath not in self.file_hashes:
                    events.append(WorkspaceChangeEvent(
                        change_type=ChangeType.CREATED,
                        file_path=fpath,
                        project_root=self.path,
                    ))
                elif self.file_hashes[fpath] != mtime:
                    events.append(WorkspaceChangeEvent(
                        change_type=ChangeType.MODIFIED,
                        file_path=fpath,
                        project_root=self.path,
                    ))

        for fpath in list(self.file_hashes.keys()):
            if fpath not in current:
                events.append(WorkspaceChangeEvent(
                    change_type=ChangeType.DELETED,
                    file_path=fpath,
                    project_root=self.path,
                ))

        self.file_hashes = current
        return events


class WorkspaceWatcher:
    """Polling-based file watcher for workspace directories.

    Uses mtime polling (no external dependencies like watchdog).
    Emits change events that can drive incremental re-indexing.
    """

    def __init__(
        self,
        poll_interval: float = 2.0,
        debounce_seconds: float = 1.0,
    ) -> None:
        self._poll_interval = poll_interval
        self._debounce_seconds = debounce_seconds
        self._directories: Dict[str, WatchedDirectory] = {}
        self._handlers: List[ChangeHandler] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def watch(self, directory_path: str) -> None:
        """Start watching a directory."""
        norm = os.path.normpath(directory_path)
        if norm not in self._directories:
            self._directories[norm] = WatchedDirectory(path=norm)
            logger.info(f"WorkspaceWatcher now watching: {norm}")

    def unwatch(self, directory_path: str) -> None:
        """Stop watching a directory."""
        norm = os.path.normpath(directory_path)
        self._directories.pop(norm, None)

    def on_change(self, handler: ChangeHandler) -> None:
        """Register a change handler."""
        self._handlers.append(handler)

    def remove_handler(self, handler: ChangeHandler) -> None:
        if handler in self._handlers:
            self._handlers.remove(handler)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("WorkspaceWatcher started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("WorkspaceWatcher stopped")

    def scan_now(self) -> List[WorkspaceChangeEvent]:
        """Force an immediate scan and return events."""
        all_events: List[WorkspaceChangeEvent] = []
        for wd in self._directories.values():
            all_events.extend(wd.scan())
        return all_events

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                all_events: List[WorkspaceChangeEvent] = []
                for wd in self._directories.values():
                    all_events.extend(wd.scan())

                if all_events:
                    debounced = self._debounce(all_events)
                    for event in debounced:
                        for handler in self._handlers:
                            try:
                                handler(event)
                            except Exception as e:
                                logger.error(
                                    f"WorkspaceWatcher handler error: {e}"
                                )

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WorkspaceWatcher poll error: {e}")
                await asyncio.sleep(self._poll_interval)

    def _debounce(
        self,
        events: List[WorkspaceChangeEvent],
    ) -> List[WorkspaceChangeEvent]:
        if not events:
            return events

        latest: Dict[str, WorkspaceChangeEvent] = {}
        for event in events:
            key = event.file_path
            if key not in latest or event.timestamp > latest[key].timestamp:
                latest[key] = event

        return list(latest.values())
