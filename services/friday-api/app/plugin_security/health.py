from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


@dataclass
class PluginSecurityHealth:
    overall_status: str = "healthy"
    trusted_publishers: int = 0
    revoked_publishers: int = 0
    total_certificates: int = 0
    total_publishers: int = 0
    blocked_publishers: int = 0
    failed_verifications: int = 0
    tampered_packages: int = 0
    repository_policies: int = 0
    repository_trust_state: str = "verified"
    signature_algorithm: str = "hmac-sha256"
    last_verification: Optional[str] = None
    violations: List[Dict[str, Any]] = field(default_factory=list)
    checked_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        d = {
            "overall_status": self.overall_status,
            "trusted_publishers": self.trusted_publishers,
            "revoked_publishers": self.revoked_publishers,
            "total_certificates": self.total_certificates,
            "total_publishers": self.total_publishers,
            "blocked_publishers": self.blocked_publishers,
            "failed_verifications": self.failed_verifications,
            "tampered_packages": self.tampered_packages,
            "repository_policies": self.repository_policies,
            "repository_trust_state": self.repository_trust_state,
            "signature_algorithm": self.signature_algorithm,
            "violations": self.violations,
            "checked_at": (self.checked_at or datetime.now(timezone.utc)).isoformat(),
        }
        if self.last_verification:
            d["last_verification"] = self.last_verification
        return d
