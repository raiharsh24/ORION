from typing import Optional
from datetime import datetime, timezone

from app.plugin_security.base import UpdateVerificationResult, SecurityCheckResult


class UpdatePolicy:
    def __init__(self):
        self._rollback_attempts: dict[str, list[str]] = {}
        self._max_rollback_count = 3
        self._require_version_increment = True

    def check_update(self, plugin_id: str, from_version: str,
                     to_version: str) -> SecurityCheckResult:
        if self._require_version_increment and from_version == to_version:
            return SecurityCheckResult.FAILED

        try:
            from_parts = [int(x) for x in from_version.split(".")]
            to_parts = [int(x) for x in to_version.split(".")]
            if to_parts < from_parts:
                return SecurityCheckResult.WARNING
            return SecurityCheckResult.PASSED
        except (ValueError, AttributeError):
            return SecurityCheckResult.SKIPPED

    def check_rollback(self, plugin_id: str, target_version: str) -> bool:
        attempts = self._rollback_attempts.get(plugin_id, [])
        if len(attempts) >= self._max_rollback_count:
            return False
        if target_version in attempts:
            return False
        attempts.append(target_version)
        self._rollback_attempts[plugin_id] = attempts
        return True

    def verify_rollback_safety(self, installed_version: str,
                                rollback_version: str) -> bool:
        try:
            installed = [int(x) for x in installed_version.split(".")]
            rollback = [int(x) for x in rollback_version.split(".")]
            return rollback < installed
        except (ValueError, AttributeError):
            return False

    def clear_rollback_history(self, plugin_id: str) -> None:
        self._rollback_attempts.pop(plugin_id, None)
