from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timezone


class PluginRuntimeState(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    REGISTERING = "registering"
    READY = "ready"
    EXECUTING = "executing"
    SUSPENDED = "suspended"
    RESUMING = "resuming"
    RELOADING = "reloading"
    UNLOADING = "unloading"
    UNLOADED = "unloaded"
    CLEANING = "cleaning"
    FAILED = "failed"


@dataclass
class ResourceQuota:
    max_memory_mb: float = 256.0
    max_cpu_seconds: float = 30.0
    max_execution_time_ms: float = 30000.0
    max_file_size_mb: float = 50.0
    max_network_requests: int = 100
    max_concurrent_tasks: int = 5


@dataclass
class SandboxConfig:
    enabled: bool = True
    restrict_imports: bool = True
    restrict_filesystem: bool = True
    restrict_network: bool = True
    restrict_subprocess: bool = True
    execution_timeout_ms: float = 30000.0
    resource_quota: ResourceQuota = field(default_factory=ResourceQuota)
    allowed_imports: Set[str] = field(default_factory=lambda: {
        "json", "yaml", "csv", "xml",
        "datetime", "time", "re", "math", "random",
        "collections", "itertools", "functools",
        "typing", "dataclasses", "enum",
        "pathlib", "os.path",
        "logging", "loguru",
    })
    blocked_imports: Set[str] = field(default_factory=lambda: {
        "ctypes", "subprocess", "multiprocessing",
        "socket", "requests", "urllib",
        "http", "ftplib", "telnetlib",
        "smtplib", "poplib", "imaplib",
        "os", "shutil", "signal",
        "sys", "importlib", "code",
        "ptrace", "bdb", "pdb",
        "inspect", "traceback",
        "asyncio", "threading", "_thread",
    })


@dataclass
class ExecutionStats:
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time_ms: float = 0.0
    average_execution_time_ms: float = 0.0
    last_execution_time: Optional[datetime] = None
    peak_memory_mb: float = 0.0
    sandbox_violations: int = 0


@dataclass
class PluginInstance:
    plugin_id: str
    name: str
    version: str = "1.0.0"
    state: PluginRuntimeState = PluginRuntimeState.DISCOVERED
    manifest_path: Optional[str] = None
    plugin_dir: Optional[str] = None
    entry_point: Optional[str] = None
    loaded_at: Optional[datetime] = None
    initialized_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    reload_count: int = 0
    execution_stats: ExecutionStats = field(default_factory=ExecutionStats)
    resource_quota: ResourceQuota = field(default_factory=ResourceQuota)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    state_history: List[Dict[str, Any]] = field(default_factory=list)

    def record_state(self, new_state: PluginRuntimeState, message: str = "") -> None:
        self.state = new_state
        self.state_history.append({
            "state": new_state.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
        })

    @property
    def is_running(self) -> bool:
        return self.state in (
            PluginRuntimeState.READY,
            PluginRuntimeState.EXECUTING,
        )

    @property
    def is_loadable(self) -> bool:
        return self.state in (
            PluginRuntimeState.DISCOVERED,
            PluginRuntimeState.VALIDATED,
            PluginRuntimeState.UNLOADED,
            PluginRuntimeState.FAILED,
        )


@dataclass
class PluginRuntimeConfig:
    plugin_dirs: List[str] = field(default_factory=lambda: ["./plugins"])
    watch_enabled: bool = True
    watch_interval_seconds: float = 5.0
    auto_load: bool = True
    auto_enable: bool = False
    sandbox_enabled: bool = True
    sandbox_config: SandboxConfig = field(default_factory=SandboxConfig)
    max_plugins: int = 50
    crash_threshold: int = 5
    crash_reset_interval_seconds: float = 300.0
    cleanup_on_unload: bool = True
    preserve_state_on_reload: bool = True
