from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class PluginState(str, Enum):
    INSTALLED = "installed"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNLOADED = "unloaded"
    REMOVED = "removed"
    FAILED = "failed"


class PluginVersion:
    @classmethod
    def parse(cls, version_str: str) -> tuple:
        parts = version_str.split(".")
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return (0, 0, 0)

    @classmethod
    def satisfies(cls, version: str, constraint: str) -> bool:
        if not constraint or constraint == "*":
            return True
        v = cls.parse(version)
        if constraint.startswith(">="):
            return v >= cls.parse(constraint[2:])
        if constraint.startswith("<="):
            return v <= cls.parse(constraint[2:])
        if constraint.startswith(">"):
            return v > cls.parse(constraint[1:])
        if constraint.startswith("<"):
            return v < cls.parse(constraint[1:])
        if constraint.startswith("=="):
            return v == cls.parse(constraint[2:])
        if constraint.startswith("^"):
            cv = cls.parse(constraint[1:])
            return v[:len(cv)] == cv
        return cls.parse(constraint) <= v


@dataclass
class PluginDependency:
    plugin_id: str
    version_constraint: str = "*"
    optional: bool = False


@dataclass
class PluginPermission:
    permission_id: str
    description: str = ""
    granted: bool = False


@dataclass
class PluginHealth:
    status: str = "unknown"
    enabled: bool = False
    loaded: bool = False
    load_time_ms: float = 0.0
    crash_count: int = 0
    last_error: Optional[str] = None
    last_loaded: Optional[datetime] = None
    last_enabled: Optional[datetime] = None


@dataclass
class Plugin:
    id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    state: PluginState = PluginState.INSTALLED
    dependencies: List[PluginDependency] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    permissions: List[PluginPermission] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    instance: Optional[Any] = None
    module_path: Optional[str] = None
    installed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_enabled(self) -> bool:
        return self.state == PluginState.ENABLED

    @property
    def is_loaded(self) -> bool:
        return self.state in (PluginState.LOADED, PluginState.INITIALIZED, PluginState.ENABLED)


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    author: str = ""
    description: str = ""
    dependencies: List[PluginDependency] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    permissions: List[PluginPermission] = field(default_factory=list)
    min_friday_version: str = "0.0.0"
    entry_point: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginMetadata:
    id: str
    name: str
    version: str
    author: str
    description: str
    state: PluginState
    dependency_count: int
    permission_count: int
    is_enabled: bool
    installed_at: datetime
