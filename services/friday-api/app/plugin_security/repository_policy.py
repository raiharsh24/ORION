from typing import Optional

from app.plugin_security.base import (
    RepositoryPolicy, RepositoryTrustPolicy, SecurityCheckResult,
)


class RepositoryPolicyManager:
    def __init__(self):
        self._policies: dict[str, RepositoryPolicy] = {}
        self._default_policy = RepositoryPolicy(
            repository_url="*",
            trust_policy=RepositoryTrustPolicy.VERIFIED_ONLY,
        )

    def set_policy(self, repository_url: str,
                   policy: RepositoryPolicy) -> None:
        self._policies[repository_url] = policy

    def get_policy(self, repository_url: str) -> RepositoryPolicy:
        if repository_url in self._policies:
            return self._policies[repository_url]
        return self._default_policy

    def set_default_policy(self, policy: RepositoryPolicy) -> None:
        self._default_policy = policy

    def check_repository_trust(self, repository_url: str,
                                publisher_id: str,
                                has_signature: bool,
                                has_integrity_hash: bool) -> SecurityCheckResult:
        policy = self.get_policy(repository_url)

        if not policy.is_publisher_allowed(publisher_id):
            return SecurityCheckResult.FAILED

        if policy.trust_policy == RepositoryTrustPolicy.STRICT:
            if not has_signature or not has_integrity_hash:
                return SecurityCheckResult.FAILED
            return SecurityCheckResult.PASSED

        if policy.trust_policy == RepositoryTrustPolicy.VERIFIED_ONLY:
            if not has_signature:
                return SecurityCheckResult.FAILED
            return SecurityCheckResult.PASSED

        if policy.trust_policy == RepositoryTrustPolicy.TRUSTED_ONLY:
            if not has_integrity_hash:
                return SecurityCheckResult.FAILED
            return SecurityCheckResult.WARNING

        if policy.require_signature and not has_signature:
            return SecurityCheckResult.FAILED

        if policy.require_integrity_hash and not has_integrity_hash:
            return SecurityCheckResult.FAILED

        return SecurityCheckResult.PASSED

    def is_unsigned_allowed(self, repository_url: str) -> bool:
        policy = self.get_policy(repository_url)
        return policy.allow_unsigned

    def list_policies(self) -> dict[str, RepositoryPolicy]:
        result = dict(self._policies)
        result["*default*"] = self._default_policy
        return result

    def remove_policy(self, repository_url: str) -> bool:
        if repository_url in self._policies:
            del self._policies[repository_url]
            return True
        return False
