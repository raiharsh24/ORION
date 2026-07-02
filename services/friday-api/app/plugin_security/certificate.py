import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.plugin_security.base import (
    CertificateInfo, CertificateStatus, SignatureAlgorithm,
)


def generate_fingerprint(publisher_id: str, public_key: str) -> str:
    raw = f"{publisher_id}:{public_key}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_certificate(
    publisher_id: str,
    publisher_name: str,
    public_key: str,
    algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256,
    validity_days: int = 365,
) -> CertificateInfo:
    now = datetime.now(timezone.utc)
    fingerprint = generate_fingerprint(publisher_id, public_key)
    return CertificateInfo(
        publisher_id=publisher_id,
        publisher_name=publisher_name,
        fingerprint=fingerprint,
        public_key=public_key,
        algorithm=algorithm,
        issued_at=now,
        expires_at=now + timedelta(days=validity_days),
        status=CertificateStatus.VALID,
    )


def check_certificate_expiry(cert: CertificateInfo) -> CertificateStatus:
    if cert.status == CertificateStatus.REVOKED:
        return CertificateStatus.REVOKED
    if cert.is_expired:
        return CertificateStatus.EXPIRED
    return CertificateStatus.VALID


def revoke_certificate(cert: CertificateInfo, reason: str = "") -> CertificateInfo:
    cert.status = CertificateStatus.REVOKED
    cert.revoked_at = datetime.now(timezone.utc)
    cert.revocation_reason = reason
    return cert


def is_certificate_valid(cert: CertificateInfo) -> bool:
    return cert.is_valid_cert


class CertificateManager:
    def __init__(self):
        self._certificates: dict[str, CertificateInfo] = {}

    def issue(self, publisher_id: str, publisher_name: str,
              public_key: str, validity_days: int = 365) -> CertificateInfo:
        cert = create_certificate(publisher_id, publisher_name, public_key,
                                   validity_days=validity_days)
        self._certificates[cert.fingerprint] = cert
        return cert

    def revoke(self, fingerprint: str, reason: str = "") -> Optional[CertificateInfo]:
        cert = self._certificates.get(fingerprint)
        if cert is None:
            return None
        return revoke_certificate(cert, reason)

    def get(self, fingerprint: str) -> Optional[CertificateInfo]:
        return self._certificates.get(fingerprint)

    def get_by_publisher(self, publisher_id: str) -> list[CertificateInfo]:
        return [c for c in self._certificates.values()
                if c.publisher_id == publisher_id]

    def check(self, fingerprint: str) -> CertificateStatus:
        cert = self._certificates.get(fingerprint)
        if cert is None:
            return CertificateStatus.UNKNOWN
        return check_certificate_expiry(cert)

    def is_valid(self, fingerprint: str) -> bool:
        return self.check(fingerprint) == CertificateStatus.VALID

    def list_all(self) -> list[CertificateInfo]:
        return list(self._certificates.values())

    def count(self) -> int:
        return len(self._certificates)
