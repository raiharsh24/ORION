from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class ToolCategory(str, Enum):
    FILESYSTEM = "filesystem"
    BROWSER = "browser"
    TERMINAL = "terminal"
    CLIPBOARD = "clipboard"
    DESKTOP = "desktop"
    GIT = "git"
    DOCKER = "docker"
    PYTHON = "python"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    WORKFLOW = "workflow"
    MISSION = "mission"
    EMAIL = "email"
    CALENDAR = "calendar"
    OCR = "ocr"
    CAMERA = "camera"
    MICROPHONE = "microphone"
    LLM = "llm"
    CUSTOM_PLUGINS = "custom_plugins"


class PermissionLevel(str, Enum):
    USER = "user"
    ELEVATED = "elevated"
    ADMIN = "admin"
    SYSTEM = "system"


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Any = None
    enum_values: Optional[List[str]] = None


@dataclass
class ToolExample:
    prompt: str
    args: Dict[str, Any]
    description: str = ""


@dataclass
class ToolHealth:
    status: str = "unknown"
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    error_count: int = 0
    success_count: int = 0
    average_latency_ms: float = 0.0


@dataclass
class ToolDependency:
    tool_id: str
    optional: bool = False
    version_requirement: Optional[str] = None


@dataclass
class ToolDefinition:
    id: str
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = "system"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    permission_level: PermissionLevel = PermissionLevel.USER
    estimated_cost: float = 0.0
    estimated_latency_ms: float = 0.0
    supports_streaming: bool = False
    supports_cancellation: bool = False
    supports_parallel_execution: bool = False
    enabled: bool = True
    parameters: List[ToolParameter] = field(default_factory=list)
    examples: List[ToolExample] = field(default_factory=list)
    health: ToolHealth = field(default_factory=ToolHealth)
    dependencies: List[ToolDependency] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
