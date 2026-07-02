import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from loguru import logger

from app.plugin_marketplace.base import (
    PluginPackage, PackageIntegrityInfo, PackageStatus,
)
from app.plugin_marketplace.manifest import (
    parse_package_manifest, manifest_to_dict, validate_manifest,
)


class PackageBuilder:
    @staticmethod
    def from_directory(path: str) -> Optional[PluginPackage]:
        base = Path(path)
        if not base.exists():
            return None
        manifest_file = base / "plugin.json"
        if not manifest_file.exists():
            manifest_file = base / "manifest.json"
        if not manifest_file.exists():
            return None
        pkg = parse_package_manifest(manifest_file)
        if pkg is None:
            return None
        pkg.install_path = str(base)
        return pkg

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Optional[PluginPackage]:
        from app.plugin_marketplace.manifest import _from_dict
        return _from_dict(data)

    @staticmethod
    def to_dict(pkg: PluginPackage) -> Dict[str, Any]:
        from app.plugin_marketplace.manifest import manifest_to_dict
        return manifest_to_dict(pkg)


class PackageIntegrity:
    @staticmethod
    def compute_hash(file_path: str, algorithm: str = "sha256") -> str:
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def verify(pkg: PluginPackage, file_path: str) -> PackageIntegrityInfo:
        info = PackageIntegrityInfo(
            expected_hash=pkg.integrity_hash,
        )
        if not pkg.integrity_hash:
            info.verified = True
            info.errors.append("No integrity hash provided, skipping verification")
            return info
        if not Path(file_path).exists():
            info.errors.append(f"File not found: {file_path}")
            return info
        actual = PackageIntegrity.compute_hash(file_path)
        info.actual_hash = actual
        info.package_size = Path(file_path).stat().st_size
        info.verified = actual == pkg.integrity_hash
        if not info.verified:
            info.errors.append(f"Hash mismatch: expected {pkg.integrity_hash}, got {actual}")
        return info
