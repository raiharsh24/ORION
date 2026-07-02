from typing import Dict, Any
from app.events.events import FridayEvent


class PluginVerified(FridayEvent):
    def __init__(self, plugin_id: str, version: str,
                 passed: bool, errors: list) -> None:
        super().__init__(topic="PluginVerified", data={
            "plugin_id": plugin_id, "version": version,
            "passed": passed, "errors": errors,
        })


class PluginRejected(FridayEvent):
    def __init__(self, plugin_id: str, version: str,
                 reason: str, details: dict) -> None:
        super().__init__(topic="PluginRejected", data={
            "plugin_id": plugin_id, "version": version,
            "reason": reason, "details": details,
        })


class PublisherTrusted(FridayEvent):
    def __init__(self, publisher_id: str, name: str,
                 trust_level: str) -> None:
        super().__init__(topic="PublisherTrusted", data={
            "publisher_id": publisher_id, "name": name,
            "trust_level": trust_level,
        })


class PublisherRevoked(FridayEvent):
    def __init__(self, publisher_id: str, name: str,
                 reason: str = "") -> None:
        super().__init__(topic="PublisherRevoked", data={
            "publisher_id": publisher_id, "name": name,
            "reason": reason,
        })


class IntegrityCheckFailed(FridayEvent):
    def __init__(self, plugin_id: str, version: str,
                 expected_hash: str, actual_hash: str) -> None:
        super().__init__(topic="IntegrityCheckFailed", data={
            "plugin_id": plugin_id, "version": version,
            "expected_hash": expected_hash, "actual_hash": actual_hash,
        })


class UpdateVerified(FridayEvent):
    def __init__(self, plugin_id: str, from_version: str,
                 to_version: str, passed: bool) -> None:
        super().__init__(topic="UpdateVerified", data={
            "plugin_id": plugin_id,
            "from_version": from_version, "to_version": to_version,
            "passed": passed,
        })


class CertificateExpired(FridayEvent):
    def __init__(self, publisher_id: str, fingerprint: str,
                 expired_at: str) -> None:
        super().__init__(topic="CertificateExpired", data={
            "publisher_id": publisher_id, "fingerprint": fingerprint,
            "expired_at": expired_at,
        })


class SecurityViolationDetected(FridayEvent):
    def __init__(self, plugin_id: str, violation_type: str,
                 severity: str, description: str) -> None:
        super().__init__(topic="SecurityViolationDetected", data={
            "plugin_id": plugin_id, "violation_type": violation_type,
            "severity": severity, "description": description,
        })
