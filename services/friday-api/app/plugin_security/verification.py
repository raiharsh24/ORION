from datetime import datetime, timezone
from typing import Optional

from app.plugin_security.base import (
    PluginSignature, SecurityVerificationResult,
    SecurityCheckResult, UpdateVerificationResult,
)
from app.plugin_marketplace.base import PluginPackage
from app.plugin_security.signature import PluginSigner, verify_plugin_signature
from app.plugin_security.trust_store import TrustStore
from app.plugin_security.repository_policy import RepositoryPolicyManager
from app.plugin_security.integrity import IntegrityVerifier


class PluginVerifier:
    def __init__(self, signer: PluginSigner,
                 trust_store: TrustStore,
                 policy_manager: RepositoryPolicyManager,
                 integrity: IntegrityVerifier):
        self._signer = signer
        self._trust_store = trust_store
        self._policy_manager = policy_manager
        self._integrity = integrity

    def verify_plugin(self, plugin: PluginPackage,
                      signature: Optional[PluginSignature] = None,
                      file_path: Optional[str] = None,
                      repository_url: str = "local") -> SecurityVerificationResult:
        result = SecurityVerificationResult(
            plugin_id=plugin.id,
            version=plugin.version,
            verified_at=datetime.now(timezone.utc),
        )

        integrity_check = SecurityCheckResult.SKIPPED
        if file_path and plugin.integrity_hash:
            integrity_check = self._integrity.verify_file(
                file_path, plugin.integrity_hash,
            )
        result.integrity_check = integrity_check

        signature_check = SecurityCheckResult.SKIPPED
        if signature and signature.is_valid:
            signature_check = self._signer.verify(signature)
        result.signature_check = signature_check

        certificate_check = SecurityCheckResult.SKIPPED
        if signature and signature.certificate_fingerprint:
            certificate_check = self._trust_store.verify_certificate(
                signature.certificate_fingerprint,
            )
        result.certificate_check = certificate_check

        publisher_check = SecurityCheckResult.SKIPPED
        if signature and signature.signed_by:
            publisher_check = self._trust_store.verify_publisher(
                signature.signed_by,
            )
        result.publisher_check = publisher_check

        repo_check = self._policy_manager.check_repository_trust(
            repository_url=repository_url,
            publisher_id=signature.signed_by if signature else "",
            has_signature=signature_check == SecurityCheckResult.PASSED,
            has_integrity_hash=integrity_check == SecurityCheckResult.PASSED,
        )
        result.repository_check = repo_check

        failures = []
        warnings = []
        if integrity_check == SecurityCheckResult.FAILED:
            failures.append("Integrity check failed: hash mismatch")
        if signature_check == SecurityCheckResult.FAILED:
            failures.append("Signature verification failed")
        if publisher_check == SecurityCheckResult.FAILED:
            failures.append("Publisher is blocked or not trusted")
        if repo_check == SecurityCheckResult.FAILED:
            failures.append("Repository trust policy rejected plugin")
        if certificate_check == SecurityCheckResult.FAILED:
            failures.append("Certificate is revoked")
        if certificate_check == SecurityCheckResult.WARNING:
            warnings.append("Certificate is expired or has issues")

        result.errors = failures
        result.warnings = warnings
        result.overall = (
            SecurityCheckResult.FAILED if failures
            else SecurityCheckResult.WARNING if warnings
            else SecurityCheckResult.PASSED
        )

        return result

    def verify_update(self, plugin_id: str,
                      from_version: str, to_version: str,
                      signature: Optional[PluginSignature] = None,
                      integrity_hash: str = "") -> UpdateVerificationResult:
        result = UpdateVerificationResult(
            plugin_id=plugin_id,
            from_version=from_version,
            to_version=to_version,
        )

        if signature and signature.is_valid:
            sig_check = self._signer.verify(signature)
            result.update_signed = sig_check == SecurityCheckResult.PASSED
            if not result.update_signed:
                result.errors.append("Update signature is invalid")

            if signature.signed_by:
                result.publisher_trusted = self._trust_store.is_publisher_allowed(
                    signature.signed_by,
                )
                if not result.publisher_trusted:
                    result.errors.append("Publisher not allowed")

                pub = self._trust_store.publishers.get(signature.signed_by)
                if pub and pub.has_valid_certificate:
                    result.certificate_valid = True

        if integrity_hash:
            result.update_hash_matches = True

        result.rollback_protection_ok = self._check_rollback_safety(
            from_version, to_version,
        )

        return result

    def _check_rollback_safety(self, from_version: str,
                                to_version: str) -> bool:
        try:
            from_parts = [int(x) for x in from_version.split(".")]
            to_parts = [int(x) for x in to_version.split(".")]
            return to_parts >= from_parts
        except (ValueError, AttributeError):
            return True
