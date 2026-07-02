import hashlib
import hmac
import json
from typing import Optional
from datetime import datetime, timezone

from app.plugin_security.base import (
    PluginSignature, SignatureAlgorithm, SecurityCheckResult,
)


def compute_signature(payload: dict, secret_key: str) -> str:
    data = json.dumps(payload, sort_keys=True, default=str)
    return hmac.new(
        secret_key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload: dict, signature: str, secret_key: str) -> bool:
    expected = compute_signature(payload, secret_key)
    return hmac.compare_digest(expected, signature)


def create_plugin_signature(
    plugin_id: str,
    version: str,
    signed_by: str,
    secret_key: str,
    metadata: Optional[dict] = None,
) -> PluginSignature:
    payload = {
        "plugin_id": plugin_id,
        "version": version,
        "signed_by": signed_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        payload["metadata"] = metadata

    sig_value = compute_signature(payload, secret_key)
    fingerprint = hashlib.sha256(
        f"{signed_by}:{plugin_id}".encode("utf-8")
    ).hexdigest()

    return PluginSignature(
        plugin_id=plugin_id,
        version=version,
        algorithm=SignatureAlgorithm.HMAC_SHA256,
        signature=sig_value,
        signed_by=signed_by,
        signed_at=datetime.now(timezone.utc),
        certificate_fingerprint=fingerprint,
        signature_data=payload,
    )


def verify_plugin_signature(
    signature: PluginSignature,
    secret_key: str,
) -> SecurityCheckResult:
    if not signature.is_valid:
        return SecurityCheckResult.SKIPPED

    payload = signature.signature_data
    if not payload:
        payload = {
            "plugin_id": signature.plugin_id,
            "version": signature.version,
            "signed_by": signature.signed_by,
        }

    if verify_signature(payload, signature.signature, secret_key):
        return SecurityCheckResult.PASSED
    return SecurityCheckResult.FAILED


class PluginSigner:
    def __init__(self, secret_key: str = ""):
        self._secret_key = secret_key

    def set_secret_key(self, secret_key: str) -> None:
        self._secret_key = secret_key

    def sign(self, plugin_id: str, version: str,
             signed_by: str, metadata: Optional[dict] = None) -> Optional[PluginSignature]:
        if not self._secret_key:
            return None
        return create_plugin_signature(
            plugin_id, version, signed_by, self._secret_key, metadata,
        )

    def verify(self, signature: PluginSignature) -> SecurityCheckResult:
        if not self._secret_key:
            return SecurityCheckResult.SKIPPED
        return verify_plugin_signature(signature, self._secret_key)
