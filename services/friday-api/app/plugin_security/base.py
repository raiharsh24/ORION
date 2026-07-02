from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class SignatureAlgorithm(str, Enum):
    HMAC_SHA256 = "hmac-sha256"
    RSA_SHA256 = "rsa-sha256"
    ECDSA_SHA256 = "ecdsa-sha256"


class CertificateStatus(str, Enum):
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class TrustLevel(str, Enum):
    UNTRUSTED = "untrusted"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


class RepositoryTrustPolicy(str, Enum):
    STRICT = "strict"
    VERIFIED_ONLY = "verified_only"
    TRUSTED_ONLY = "trusted_only"
    PERMISSIVE = "permissive"


class SecurityCheckResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class PluginSignature:
    plugin_id: str
    version: str
    algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    signature: str = ""
    signed_by: str = ""
    signed_at: Optional[datetime] = None
    certificate_fingerprint: str = ""
    hash_algorithm: str = "sha256"
    signature_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return bool(self.signature) and bool(self.signed_by)


@dataclass
class CertificateInfo:
    publisher_id: str
    publisher_name: str
    fingerprint: str
    public_key: str
    algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: CertificateStatus = CertificateStatus.UNKNOWN
    revoked_at: Optional[datetime] = None
    revocation_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.status == CertificateStatus.REVOKED

    @property
    def is_valid_cert(self) -> bool:
        return (
            self.status == CertificateStatus.VALID
            and not self.is_expired
            and not self.is_revoked
        )


@dataclass
class PublisherInfo:
    publisher_id: str
    name: str
    email: str = ""
    website: str = ""
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    certificates: List[CertificateInfo] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_trusted(self) -> bool:
        return self.trust_level in (TrustLevel.MEDIUM, TrustLevel.HIGH, TrustLevel.VERIFIED)

    @property
    def has_valid_certificate(self) -> bool:
        return any(c.is_valid_cert for c in self.certificates)


@dataclass
class SecurityVerificationResult:
    plugin_id: str
    version: str
    integrity_check: SecurityCheckResult = SecurityCheckResult.SKIPPED
    signature_check: SecurityCheckResult = SecurityCheckResult.SKIPPED
    certificate_check: SecurityCheckResult = SecurityCheckResult.SKIPPED
    publisher_check: SecurityCheckResult = SecurityCheckResult.SKIPPED
    repository_check: SecurityCheckResult = SecurityCheckResult.SKIPPED
    overall: SecurityCheckResult = SecurityCheckResult.SKIPPED
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    verified_at: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.overall in (SecurityCheckResult.PASSED, SecurityCheckResult.SKIPPED)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


@dataclass
class SecurityViolation:
    plugin_id: str
    violation_type: str
    severity: str = "medium"
    description: str = ""
    detected_at: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepositoryPolicy:
    repository_url: str
    trust_policy: RepositoryTrustPolicy = RepositoryTrustPolicy.VERIFIED_ONLY
    allowed_publishers: List[str] = field(default_factory=list)
    blocked_publishers: List[str] = field(default_factory=list)
    require_signature: bool = True
    require_integrity_hash: bool = True
    require_certificate: bool = False
    max_certificate_age_days: int = 365
    allow_unsigned: bool = False
    allow_expired_certificates: bool = False
    auto_block_revoked: bool = True

    def is_publisher_allowed(self, publisher_id: str) -> bool:
        if publisher_id in self.blocked_publishers:
            return False
        if self.allowed_publishers and publisher_id not in self.allowed_publishers:
            return False
        return True


@dataclass
class UpdateVerificationResult:
    plugin_id: str
    from_version: str
    to_version: str
    rollback_allowed: bool = False
    update_signed: bool = False
    update_hash_matches: bool = False
    publisher_trusted: bool = False
    certificate_valid: bool = False
    rollback_protection_ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        return not self.errors and self.update_signed and self.update_hash_matches
