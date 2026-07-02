import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

from app.plugin_marketplace.base import PluginPackage, PackageDependency


def parse_package_manifest(path: Path) -> Optional[PluginPackage]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _from_dict(data, str(path))
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Failed to parse manifest '{path}': {e}")
        return None


def _from_dict(data: Dict[str, Any], source_path: str = "") -> PluginPackage:
    deps = []
    for d in data.get("dependencies", []):
        deps.append(PackageDependency(
            plugin_id=d.get("plugin_id", d.get("id", "")),
            version_constraint=d.get("version", ">=1.0.0"),
            optional=d.get("optional", False),
        ))
    opt_deps = []
    for d in data.get("optionalDependencies", data.get("optional_dependencies", [])):
        opt_deps.append(PackageDependency(
            plugin_id=d.get("plugin_id", d.get("id", "")),
            version_constraint=d.get("version", ">=1.0.0"),
            optional=True,
        ))
    return PluginPackage(
        id=data["id"],
        name=data.get("name", data["id"]),
        version=data.get("version", "1.0.0"),
        author=data.get("author", ""),
        license=data.get("license", ""),
        homepage=data.get("homepage", ""),
        documentation=data.get("documentation", ""),
        description=data.get("description", ""),
        min_friday_version=data.get("minFridayVersion", data.get("min_friday_version", "")),
        max_friday_version=data.get("maxFridayVersion", data.get("max_friday_version", "")),
        dependencies=deps,
        optional_dependencies=opt_deps,
        permissions=data.get("permissions", []),
        required_capabilities=data.get("requiredCapabilities", data.get("required_capabilities", [])),
        entry_point=data.get("entryPoint", data.get("entry_point", "")),
        categories=data.get("categories", []),
        tags=data.get("tags", []),
        metadata=data.get("metadata", {}),
        integrity_hash=data.get("integrityHash", data.get("integrity_hash", "")),
        package_size=data.get("packageSize", data.get("package_size", 0)),
        source=data.get("source", "local"),
        rating=float(data.get("rating", 0)),
        download_count=data.get("downloadCount", data.get("download_count", 0)),
        featured=data.get("featured", False),
        icon_url=data.get("iconUrl", data.get("icon_url", "")),
        screenshots=data.get("screenshots", []),
    )


def manifest_to_dict(pkg: PluginPackage) -> Dict[str, Any]:
    return {
        "id": pkg.id,
        "name": pkg.name,
        "version": pkg.version,
        "author": pkg.author,
        "license": pkg.license,
        "homepage": pkg.homepage,
        "documentation": pkg.documentation,
        "description": pkg.description,
        "minFridayVersion": pkg.min_friday_version,
        "maxFridayVersion": pkg.max_friday_version,
        "dependencies": [
            {"plugin_id": d.plugin_id, "version": d.version_constraint,
             "optional": d.optional}
            for d in pkg.dependencies
        ],
        "optionalDependencies": [
            {"plugin_id": d.plugin_id, "version": d.version_constraint}
            for d in pkg.optional_dependencies
        ],
        "permissions": pkg.permissions,
        "requiredCapabilities": pkg.required_capabilities,
        "entryPoint": pkg.entry_point,
        "categories": pkg.categories,
        "tags": pkg.tags,
        "metadata": pkg.metadata,
        "integrityHash": pkg.integrity_hash,
        "packageSize": pkg.package_size,
        "rating": pkg.rating,
        "downloadCount": pkg.download_count,
        "featured": pkg.featured,
        "iconUrl": pkg.icon_url,
        "screenshots": pkg.screenshots,
    }


def validate_manifest(pkg: PluginPackage) -> List[str]:
    errors = []
    if not pkg.id:
        errors.append("Missing required field: id")
    if not pkg.name:
        errors.append("Missing required field: name")
    if not pkg.version:
        errors.append("Missing required field: version")
    else:
        parts = pkg.version.split(".")
        try:
            tuple(int(p) for p in parts)
        except ValueError:
            errors.append(f"Invalid version format: '{pkg.version}'")
    if pkg.min_friday_version:
        parts = pkg.min_friday_version.split(".")
        try:
            tuple(int(p) for p in parts)
        except ValueError:
            errors.append(f"Invalid minFridayVersion: '{pkg.min_friday_version}'")
    return errors
