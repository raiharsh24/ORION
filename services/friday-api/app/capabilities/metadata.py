from typing import List
from datetime import datetime, timezone

from app.capabilities.base import (
    CapabilityDefinition, CapabilityMetadata, CapabilityCategory, CapabilityStatus,
)


def build_metadata(defn: CapabilityDefinition) -> CapabilityMetadata:
    return CapabilityMetadata(
        id=defn.id,
        name=defn.name,
        description=defn.description,
        category=defn.category,
        version=defn.version,
        status=defn.status,
        aliases=list(defn.aliases),
        tags=list(defn.tags),
        tool_count=len(defn.tool_ids),
        dependency_count=len(defn.dependencies),
        registered_at=defn.registered_at,
    )
