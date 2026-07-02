import hashlib
import os
from typing import Optional

from app.plugin_security.base import SecurityCheckResult


def compute_sha256(file_path: str, chunk_size: int = 65536) -> Optional[str]:
    if not os.path.isfile(file_path):
        return None
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def compute_sha256_from_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_file_integrity(file_path: str, expected_hash: str) -> SecurityCheckResult:
    actual = compute_sha256(file_path)
    if actual is None:
        return SecurityCheckResult.FAILED
    if actual == expected_hash:
        return SecurityCheckResult.PASSED
    return SecurityCheckResult.FAILED


def verify_data_integrity(data: bytes, expected_hash: str) -> SecurityCheckResult:
    actual = compute_sha256_from_bytes(data)
    if actual == expected_hash:
        return SecurityCheckResult.PASSED
    return SecurityCheckResult.FAILED


class IntegrityVerifier:
    def __init__(self):
        self._verified: dict[str, str] = {}

    def verify_file(self, file_path: str,
                    expected_hash: str) -> SecurityCheckResult:
        result = verify_file_integrity(file_path, expected_hash)
        if result == SecurityCheckResult.PASSED:
            self._verified[file_path] = expected_hash
        return result

    def verify_data(self, data: bytes,
                    expected_hash: str) -> SecurityCheckResult:
        result = verify_data_integrity(data, expected_hash)
        if result == SecurityCheckResult.PASSED:
            self._verified[hash(data)] = expected_hash
        return result

    def compute(self, file_path: str) -> Optional[str]:
        return compute_sha256(file_path)

    def is_verified(self, file_path: str) -> bool:
        return file_path in self._verified

    def clear(self) -> None:
        self._verified.clear()
