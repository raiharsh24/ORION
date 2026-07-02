from datetime import datetime, timezone
from typing import Optional

from app.plugin_security.base import (
    CertificateInfo, PublisherInfo, TrustLevel,
    SecurityCheckResult,
)
from app.plugin_security.certificate import CertificateManager
from app.plugin_security.publisher import PublisherRegistry


class TrustStore:
    def __init__(self):
        self._certificates = CertificateManager()
        self._publishers = PublisherRegistry()
        self._blocked_publishers: set[str] = set()
        self._allowed_publishers: set[str] = set()

    @property
    def certificates(self) -> CertificateManager:
        return self._certificates

    @property
    def publishers(self) -> PublisherRegistry:
        return self._publishers

    def trust_publisher(self, publisher_id: str) -> bool:
        return self._publishers.trust(publisher_id)

    def revoke_publisher(self, publisher_id: str) -> bool:
        return self._publishers.revoke_trust(publisher_id)

    def block_publisher(self, publisher_id: str) -> None:
        self._blocked_publishers.add(publisher_id)

    def unblock_publisher(self, publisher_id: str) -> bool:
        return self._blocked_publishers.discard(publisher_id) or True

    def is_publisher_blocked(self, publisher_id: str) -> bool:
        return publisher_id in self._blocked_publishers

    def allow_publisher(self, publisher_id: str) -> None:
        self._allowed_publishers.add(publisher_id)

    def is_publisher_allowed(self, publisher_id: str) -> bool:
        if self._allowed_publishers and publisher_id not in self._allowed_publishers:
            return False
        return publisher_id not in self._blocked_publishers

    def verify_publisher(self, publisher_id: str) -> SecurityCheckResult:
        if self.is_publisher_blocked(publisher_id):
            return SecurityCheckResult.FAILED
        if not self.is_publisher_allowed(publisher_id):
            return SecurityCheckResult.FAILED
        pub = self._publishers.get(publisher_id)
        if pub is None:
            return SecurityCheckResult.SKIPPED
        if pub.trust_level == TrustLevel.UNTRUSTED:
            return SecurityCheckResult.FAILED
        if pub.is_trusted:
            if pub.has_valid_certificate:
                return SecurityCheckResult.PASSED
            return SecurityCheckResult.WARNING
        return SecurityCheckResult.SKIPPED

    def verify_certificate(self, fingerprint: str) -> SecurityCheckResult:
        cert = self._certificates.get(fingerprint)
        if cert is None:
            return SecurityCheckResult.SKIPPED
        if cert.is_revoked:
            return SecurityCheckResult.FAILED
        if cert.is_expired:
            return SecurityCheckResult.WARNING
        if cert.is_valid_cert:
            return SecurityCheckResult.PASSED
        return SecurityCheckResult.WARNING

    def get_trusted_publishers(self) -> list[PublisherInfo]:
        return self._publishers.get_trusted_publishers()

    def get_revoked_publishers(self) -> list[PublisherInfo]:
        return self._publishers.get_revoked_publishers()

    def health(self) -> dict:
        return {
            "trusted_publishers": len(self.get_trusted_publishers()),
            "revoked_publishers": len(self.get_revoked_publishers()),
            "total_publishers": self._publishers.count(),
            "total_certificates": self._certificates.count(),
            "blocked_publishers": len(self._blocked_publishers),
        }
