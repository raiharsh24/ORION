from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone


class CapabilityCategory(str, Enum):
    WEB_SEARCH = "web_search"
    FILE_ANALYSIS = "file_analysis"
    DESKTOP_AUTOMATION = "desktop_automation"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    MEMORY_ACCESS = "memory_access"
    VISION = "vision"
    VOICE = "voice"
    TERMINAL = "terminal"
    WORKFLOW_CONTROL = "workflow_control"
    BROWSER = "browser"
    CODE_EXECUTION = "code_execution"
    SYSTEM = "system"
    COMMUNICATION = "communication"
    DATA_PROCESSING = "data_processing"
    MONITORING = "monitoring"
    CUSTOM = "custom"


class CapabilityStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


@dataclass
class CapabilityDependency:
    capability_id: str
    optional: bool = False
    version_constraint: Optional[str] = None


@dataclass
class CapabilityDefinition:
    id: str
    name: str
    description: str
    category: CapabilityCategory = CapabilityCategory.CUSTOM
    version: str = "1.0.0"
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    aliases: List[str] = field(default_factory=list)
    tool_ids: List[str] = field(default_factory=list)
    recommended_tool_ids: List[str] = field(default_factory=list)
    dependencies: List[CapabilityDependency] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    permission_level: str = "user"
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CapabilityMetadata:
    id: str
    name: str
    description: str
    category: CapabilityCategory
    version: str
    status: CapabilityStatus
    aliases: List[str]
    tags: List[str]
    tool_count: int
    dependency_count: int
    registered_at: datetime


@dataclass
class CapabilityHealth:
    availability: bool = True
    status: str = "unknown"
    dependency_status: str = "unknown"
    registered_tools: int = 0
    available_tools: int = 0
    execution_success_count: int = 0
    execution_failure_count: int = 0
    last_execution: Optional[datetime] = None
    version: str = "1.0.0"
    message: str = ""


@dataclass
class CapabilityResult:
    capability_id: str
    success: bool = False
    output: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    tool_results: Dict[str, Any] = field(default_factory=dict)
    resolved_tool_ids: List[str] = field(default_factory=list)
    resolved_dependencies: List[str] = field(default_factory=list)


@dataclass
class CapabilityPermission:
    capability_id: str
    required_level: str = "user"
    allowed_users: List[str] = field(default_factory=list)
    allowed_roles: List[str] = field(default_factory=list)


@dataclass
class CapabilityResolution:
    capability_id: str
    capability_name: str
    resolved_tool_ids: List[str] = field(default_factory=list)
    resolved_dependencies: List[str] = field(default_factory=list)
    confidence: float = 1.0
    resolution_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
