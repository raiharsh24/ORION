from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.tools.base import ToolCategory, PermissionLevel, ToolDependency, ToolHealth


@dataclass
class ToolMetadata:
    id: str
    name: str
    description: str
    category: ToolCategory
    version: str
    author: str
    tags: List[str]
    permission_level: PermissionLevel
    estimated_cost: float
    estimated_latency_ms: float
    supports_streaming: bool
    supports_cancellation: bool
    supports_parallel_execution: bool
    dependencies: List[ToolDependency]
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_definition(cls, definition: "ToolDefinition") -> "ToolMetadata":
        return cls(
            id=definition.id,
            name=definition.name,
            description=definition.description,
            category=definition.category,
            version=definition.version,
            author=definition.author,
            tags=list(definition.tags),
            permission_level=definition.permission_level,
            estimated_cost=definition.estimated_cost,
            estimated_latency_ms=definition.estimated_latency_ms,
            supports_streaming=definition.supports_streaming,
            supports_cancellation=definition.supports_cancellation,
            supports_parallel_execution=definition.supports_parallel_execution,
            dependencies=list(definition.dependencies),
            input_schema=dict(definition.input_schema),
            output_schema=dict(definition.output_schema),
            registered_at=definition.registered_at,
            updated_at=definition.updated_at,
        )
