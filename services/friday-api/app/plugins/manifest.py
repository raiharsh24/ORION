import json
from typing import Optional, List
from pathlib import Path

from app.plugins.base import (
    PluginManifest, PluginDependency, PluginPermission,
)


def parse_manifest(path: Path) -> Optional[PluginManifest]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return manifest_from_dict(data)


def manifest_from_dict(data: dict) -> Optional[PluginManifest]:
    if not isinstance(data, dict):
        return None
    try:
        deps = []
        for d in data.get("dependencies", []):
            deps.append(PluginDependency(
                plugin_id=d.get("id", ""),
                version_constraint=d.get("version", "*"),
                optional=d.get("optional", False),
            ))
        perms = []
        for p in data.get("permissions", []):
            perms.append(PluginPermission(
                permission_id=p.get("id", ""),
                description=p.get("description", ""),
                granted=False,
            ))
        return PluginManifest(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            version=str(data.get("version", "1.0.0")),
            author=str(data.get("author", "")),
            description=str(data.get("description", "")),
            dependencies=deps,
            required_capabilities=list(data.get("required_capabilities", [])),
            permissions=perms,
            min_friday_version=str(data.get("min_friday_version", "0.0.0")),
            entry_point=str(data.get("entry_point", "")),
            metadata=dict(data.get("metadata", {})),
        )
    except (KeyError, TypeError, ValueError):
        return None


def validate_manifest(manifest: PluginManifest) -> List[str]:
    errors = []
    if not manifest.id:
        errors.append("Plugin id is required")
    if not manifest.name:
        errors.append("Plugin name is required")
    if not manifest.version:
        errors.append("Plugin version is required")
    parts = manifest.version.split(".")
    if len(parts) != 3:
        errors.append(f"Invalid version format: '{manifest.version}' (expected X.Y.Z)")
    else:
        for p in parts:
            if not p.isdigit():
                errors.append(f"Invalid version component: '{p}'")
    return errors
