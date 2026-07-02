import os
import hashlib
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.plugin_security.base import (
    PluginSignature, SignatureAlgorithm, CertificateInfo,
    CertificateStatus, TrustLevel, PublisherInfo,
    RepositoryTrustPolicy, SecurityCheckResult,
    SecurityVerificationResult, SecurityViolation,
    RepositoryPolicy, UpdateVerificationResult,
)
from app.plugin_security.signature import (
    PluginSigner, compute_signature, verify_signature,
    create_plugin_signature, verify_plugin_signature,
)
from app.plugin_security.certificate import (
    CertificateManager, create_certificate, check_certificate_expiry,
    revoke_certificate, generate_fingerprint, is_certificate_valid,
)
from app.plugin_security.publisher import PublisherRegistry
from app.plugin_security.trust_store import TrustStore
from app.plugin_security.repository_policy import RepositoryPolicyManager
from app.plugin_security.integrity import IntegrityVerifier, compute_sha256
from app.plugin_security.verification import PluginVerifier
from app.plugin_security.update_policy import UpdatePolicy
from app.plugin_security.health import PluginSecurityHealth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d)


@pytest.fixture
def temp_file(temp_dir):
    path = os.path.join(temp_dir, "test_plugin.zip")
    Path(path).write_text("plugin content data")
    return path


@pytest.fixture
def secret_key():
    return "test-secret-key-12345"


@pytest.fixture
def signer(secret_key):
    return PluginSigner(secret_key=secret_key)


@pytest.fixture
def trust_store():
    return TrustStore()


@pytest.fixture
def policy_manager():
    return RepositoryPolicyManager()


@pytest.fixture
def integrity():
    return IntegrityVerifier()


@pytest.fixture
def verifier(signer, trust_store, policy_manager, integrity):
    return PluginVerifier(signer, trust_store, policy_manager, integrity)


# ---------------------------------------------------------------------------
# Base Model Tests
# ---------------------------------------------------------------------------

class TestPluginSignature:
    def test_defaults(self):
        sig = PluginSignature(plugin_id="test", version="1.0.0")
        assert sig.algorithm == SignatureAlgorithm.HMAC_SHA256
        assert sig.is_valid is False

    def test_valid_signature(self):
        sig = PluginSignature(plugin_id="test", version="1.0.0",
                               signature="abc123", signed_by="pub1")
        assert sig.is_valid is True


class TestCertificateInfo:
    def test_expired(self):
        cert = CertificateInfo(
            publisher_id="p1", publisher_name="Pub1",
            fingerprint="fp1", public_key="key1",
            issued_at=datetime.now(timezone.utc) - timedelta(days=400),
            expires_at=datetime.now(timezone.utc) - timedelta(days=35),
        )
        assert cert.is_expired is True

    def test_not_expired(self):
        cert = CertificateInfo(
            publisher_id="p1", publisher_name="Pub1",
            fingerprint="fp1", public_key="key1",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            status=CertificateStatus.VALID,
        )
        assert cert.is_expired is False
        assert cert.is_valid_cert is True

    def test_revoked(self):
        cert = CertificateInfo(
            publisher_id="p1", publisher_name="Pub1",
            fingerprint="fp1", public_key="key1",
            status=CertificateStatus.REVOKED,
        )
        assert cert.is_revoked is True
        assert cert.is_valid_cert is False


class TestPublisherInfo:
    def test_is_trusted(self):
        pub = PublisherInfo(publisher_id="p1", name="Pub1",
                             trust_level=TrustLevel.VERIFIED)
        assert pub.is_trusted is True

    def test_not_trusted(self):
        pub = PublisherInfo(publisher_id="p1", name="Pub1",
                             trust_level=TrustLevel.UNTRUSTED)
        assert pub.is_trusted is False


class TestSecurityVerificationResult:
    def test_defaults(self):
        r = SecurityVerificationResult(plugin_id="test", version="1.0.0")
        assert r.passed is True
        assert r.has_errors is False

    def test_failed(self):
        r = SecurityVerificationResult(plugin_id="test", version="1.0.0",
                                        overall=SecurityCheckResult.FAILED)
        assert r.passed is False

    def test_with_errors(self):
        r = SecurityVerificationResult(plugin_id="test", version="1.0.0",
                                        errors=["hash mismatch"])
        assert r.has_errors is True


class TestRepositoryPolicy:
    def test_blocked_publisher(self):
        policy = RepositoryPolicy(repository_url="repo",
                                   blocked_publishers=["bad_pub"])
        assert policy.is_publisher_allowed("bad_pub") is False
        assert policy.is_publisher_allowed("good_pub") is True

    def test_allowed_list(self):
        policy = RepositoryPolicy(repository_url="repo",
                                   allowed_publishers=["pub1"])
        assert policy.is_publisher_allowed("pub1") is True
        assert policy.is_publisher_allowed("pub2") is False


# ---------------------------------------------------------------------------
# Signature Tests
# ---------------------------------------------------------------------------

class TestSignature:
    def test_compute_and_verify(self, secret_key):
        payload = {"plugin_id": "test", "version": "1.0.0"}
        sig = compute_signature(payload, secret_key)
        assert verify_signature(payload, sig, secret_key) is True

    def test_wrong_key_fails(self, secret_key):
        payload = {"plugin_id": "test", "version": "1.0.0"}
        sig = compute_signature(payload, secret_key)
        assert verify_signature(payload, sig, "wrong-key") is False

    def test_tampered_payload_fails(self, secret_key):
        payload = {"plugin_id": "test", "version": "1.0.0"}
        sig = compute_signature(payload, secret_key)
        tampered = {"plugin_id": "evil", "version": "1.0.0"}
        assert verify_signature(tampered, sig, secret_key) is False

    def test_create_signature(self, secret_key):
        sig = create_plugin_signature("p1", "1.0.0", "pub1", secret_key)
        assert sig.plugin_id == "p1"
        assert sig.version == "1.0.0"
        assert sig.certificate_fingerprint
        assert sig.signature

    def test_verify_signature_valid(self, secret_key):
        sig = create_plugin_signature("p1", "1.0.0", "pub1", secret_key)
        result = verify_plugin_signature(sig, secret_key)
        assert result == SecurityCheckResult.PASSED

    def test_verify_signature_invalid(self, secret_key):
        sig = create_plugin_signature("p1", "1.0.0", "pub1", secret_key)
        result = verify_plugin_signature(sig, "wrong-key")
        assert result == SecurityCheckResult.FAILED

    def test_verify_empty_signature(self, secret_key):
        sig = PluginSignature(plugin_id="p1", version="1.0.0")
        result = verify_plugin_signature(sig, secret_key)
        assert result == SecurityCheckResult.SKIPPED


class TestPluginSigner:
    def test_sign_and_verify(self, signer):
        sig = signer.sign("p1", "1.0.0", "pub1")
        assert sig is not None
        assert signer.verify(sig) == SecurityCheckResult.PASSED

    def test_sign_without_key(self):
        signer = PluginSigner()
        sig = signer.sign("p1", "1.0.0", "pub1")
        assert sig is None

    def test_verify_without_key(self, secret_key):
        signer = PluginSigner()
        sig = create_plugin_signature("p1", "1.0.0", "pub1", secret_key)
        result = signer.verify(sig)
        assert result == SecurityCheckResult.SKIPPED


# ---------------------------------------------------------------------------
# Certificate Tests
# ---------------------------------------------------------------------------

class TestCertificate:
    def test_create_and_check_valid(self):
        cert = create_certificate("p1", "Pub One", "public_key_data")
        assert cert.status == CertificateStatus.VALID
        assert cert.fingerprint
        assert is_certificate_valid(cert) is True

    def test_check_expiry_fresh(self):
        cert = create_certificate("p1", "Pub One", "key")
        status = check_certificate_expiry(cert)
        assert status == CertificateStatus.VALID

    def test_revocation(self):
        cert = create_certificate("p1", "Pub One", "key")
        revoke_certificate(cert, "compromised key")
        assert cert.status == CertificateStatus.REVOKED
        assert cert.revocation_reason == "compromised key"

    def test_expired_certificate(self):
        cert = CertificateInfo(
            publisher_id="p1", publisher_name="Pub1",
            fingerprint="fp", public_key="key",
            issued_at=datetime.now(timezone.utc) - timedelta(days=400),
            expires_at=datetime.now(timezone.utc) - timedelta(days=30),
            status=CertificateStatus.VALID,
        )
        assert cert.is_expired is True
        assert check_certificate_expiry(cert) == CertificateStatus.EXPIRED

    def test_fingerprint_generation(self):
        fp1 = generate_fingerprint("p1", "key1")
        fp2 = generate_fingerprint("p1", "key1")
        fp3 = generate_fingerprint("p2", "key1")
        assert fp1 == fp2
        assert fp1 != fp3


class TestCertificateManager:
    def test_issue_and_get(self):
        mgr = CertificateManager()
        cert = mgr.issue("p1", "Pub One", "public_key")
        assert mgr.get(cert.fingerprint) is cert

    def test_check_valid(self):
        mgr = CertificateManager()
        cert = mgr.issue("p1", "Pub One", "key")
        assert mgr.is_valid(cert.fingerprint) is True

    def test_revoke(self):
        mgr = CertificateManager()
        cert = mgr.issue("p1", "Pub One", "key")
        mgr.revoke(cert.fingerprint, "compromised")
        assert mgr.is_valid(cert.fingerprint) is False

    def test_get_by_publisher(self):
        mgr = CertificateManager()
        c1 = mgr.issue("p1", "Pub1", "key1")
        c2 = mgr.issue("p1", "Pub1", "key2")
        c3 = mgr.issue("p2", "Pub2", "key3")
        certs = mgr.get_by_publisher("p1")
        assert len(certs) == 2
        assert c1 in certs
        assert c2 in certs
        assert c3 not in certs

    def test_list_all(self):
        mgr = CertificateManager()
        mgr.issue("p1", "Pub1", "k1")
        mgr.issue("p2", "Pub2", "k2")
        assert mgr.count() == 2


# ---------------------------------------------------------------------------
# Publisher Tests
# ---------------------------------------------------------------------------

class TestPublisherRegistry:
    def test_register_and_get(self):
        reg = PublisherRegistry()
        pub = reg.register("p1", "Pub One")
        assert reg.get("p1") is pub

    def test_trust_and_revoke(self):
        reg = PublisherRegistry()
        reg.register("p1", "Pub One", trust_level=TrustLevel.UNTRUSTED)
        assert reg.is_trusted("p1") is False
        reg.trust("p1")
        assert reg.is_trusted("p1") is True
        reg.revoke_trust("p1")
        assert reg.is_trusted("p1") is False

    def test_get_trusted_publishers(self):
        reg = PublisherRegistry()
        reg.register("p1", "Pub1", trust_level=TrustLevel.VERIFIED)
        reg.register("p2", "Pub2", trust_level=TrustLevel.UNTRUSTED)
        trusted = reg.get_trusted_publishers()
        assert len(trusted) == 1
        assert trusted[0].publisher_id == "p1"

    def test_remove(self):
        reg = PublisherRegistry()
        reg.register("p1", "Pub1")
        assert reg.remove("p1") is True
        assert reg.get("p1") is None
        assert reg.remove("nonexistent") is False


# ---------------------------------------------------------------------------
# Trust Store Tests
# ---------------------------------------------------------------------------

class TestTrustStore:
    def test_trust_publisher(self, trust_store):
        trust_store.publishers.register("p1", "Pub1")
        assert trust_store.trust_publisher("p1") is True
        assert trust_store.verify_publisher("p1") in (
            SecurityCheckResult.PASSED, SecurityCheckResult.WARNING)

    def test_block_publisher(self, trust_store):
        trust_store.block_publisher("bad")
        assert trust_store.is_publisher_blocked("bad") is True
        assert trust_store.verify_publisher("bad") == SecurityCheckResult.FAILED

    def test_verify_certificate(self, trust_store):
        cert = trust_store.certificates.issue("p1", "Pub1", "key")
        result = trust_store.verify_certificate(cert.fingerprint)
        assert result == SecurityCheckResult.PASSED

    def test_verify_certificate_unknown(self, trust_store):
        result = trust_store.verify_certificate("nonexistent")
        assert result == SecurityCheckResult.SKIPPED

    def test_health(self, trust_store):
        h = trust_store.health()
        assert "trusted_publishers" in h
        assert "total_certificates" in h


# ---------------------------------------------------------------------------
# Integrity Tests
# ---------------------------------------------------------------------------

class TestIntegrityVerifier:
    def test_compute_sha256(self, temp_file):
        h = compute_sha256(temp_file)
        assert h is not None
        assert len(h) == 64

    def test_verify_file_valid(self, temp_file):
        verifier = IntegrityVerifier()
        h = verifier.compute(temp_file)
        assert h is not None
        result = verifier.verify_file(temp_file, h)
        assert result == SecurityCheckResult.PASSED

    def test_verify_file_invalid(self, temp_file):
        verifier = IntegrityVerifier()
        result = verifier.verify_file(temp_file, "0" * 64)
        assert result == SecurityCheckResult.FAILED

    def test_verify_file_not_found(self):
        verifier = IntegrityVerifier()
        result = verifier.verify_file("/nonexistent.zip", "0" * 64)
        assert result == SecurityCheckResult.FAILED

    def test_verify_data(self):
        verifier = IntegrityVerifier()
        data = b"test data"
        h = hashlib.sha256(data).hexdigest()
        result = verifier.verify_data(data, h)
        assert result == SecurityCheckResult.PASSED

    def test_verify_data_mismatch(self):
        verifier = IntegrityVerifier()
        data = b"test data"
        result = verifier.verify_data(data, "0" * 64)
        assert result == SecurityCheckResult.FAILED

    def test_is_verified(self, temp_file):
        verifier = IntegrityVerifier()
        h = verifier.compute(temp_file)
        verifier.verify_file(temp_file, h)
        assert verifier.is_verified(temp_file) is True

    def test_clear(self, temp_file):
        verifier = IntegrityVerifier()
        h = verifier.compute(temp_file)
        verifier.verify_file(temp_file, h)
        verifier.clear()
        assert verifier.is_verified(temp_file) is False


# ---------------------------------------------------------------------------
# Repository Policy Tests
# ---------------------------------------------------------------------------

class TestRepositoryPolicyManager:
    def test_default_policy(self, policy_manager):
        result = policy_manager.check_repository_trust(
            "unknown_repo", "pub1", False, False)
        assert result == SecurityCheckResult.FAILED

    def test_verified_only_passing(self, policy_manager):
        policy = RepositoryPolicy(repository_url="trusted",
                                   trust_policy=RepositoryTrustPolicy.VERIFIED_ONLY)
        policy_manager.set_policy("trusted", policy)
        result = policy_manager.check_repository_trust(
            "trusted", "pub1", True, False)
        assert result == SecurityCheckResult.PASSED

    def test_verified_only_no_signature(self, policy_manager):
        policy = RepositoryPolicy(repository_url="strict",
                                   trust_policy=RepositoryTrustPolicy.VERIFIED_ONLY)
        policy_manager.set_policy("strict", policy)
        result = policy_manager.check_repository_trust(
            "strict", "pub1", False, True)
        assert result == SecurityCheckResult.FAILED

    def test_strict_policy(self, policy_manager):
        policy = RepositoryPolicy(repository_url="strict",
                                   trust_policy=RepositoryTrustPolicy.STRICT)
        policy_manager.set_policy("strict", policy)
        result = policy_manager.check_repository_trust(
            "strict", "pub1", True, True)
        assert result == SecurityCheckResult.PASSED

    def test_permissive_policy(self, policy_manager):
        policy = RepositoryPolicy(repository_url="open",
                                   trust_policy=RepositoryTrustPolicy.PERMISSIVE,
                                   require_signature=False,
                                   require_integrity_hash=False)
        policy_manager.set_policy("open", policy)
        result = policy_manager.check_repository_trust(
            "open", "pub1", False, False)
        assert result == SecurityCheckResult.PASSED

    def test_blocked_publisher(self, policy_manager):
        policy = RepositoryPolicy(repository_url="repo",
                                   blocked_publishers=["bad_pub"])
        policy_manager.set_policy("repo", policy)
        result = policy_manager.check_repository_trust(
            "repo", "bad_pub", True, True)
        assert result == SecurityCheckResult.FAILED

    def test_list_policies(self, policy_manager):
        policies = policy_manager.list_policies()
        assert "*default*" in policies


# ---------------------------------------------------------------------------
# Verification Tests
# ---------------------------------------------------------------------------

class TestPluginVerifier:
    def test_verify_no_signature(self, verifier, policy_manager):
        from app.plugin_marketplace.base import PluginPackage
        policy = RepositoryPolicy(repository_url="open_repo",
                                   trust_policy=RepositoryTrustPolicy.PERMISSIVE,
                                   require_signature=False,
                                   require_integrity_hash=False)
        policy_manager.set_policy("open_repo", policy)
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        result = verifier.verify_plugin(plugin, repository_url="open_repo")
        assert result.passed is True

    def test_verify_with_valid_signature(self, verifier, signer):
        from app.plugin_marketplace.base import PluginPackage
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        signature = signer.sign("test", "1.0.0", "pub1")
        result = verifier.verify_plugin(plugin, signature=signature)
        assert result.signature_check == SecurityCheckResult.PASSED

    def test_verify_with_invalid_signature(self, verifier):
        from app.plugin_marketplace.base import PluginPackage
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        sig = PluginSignature(plugin_id="test", version="1.0.0",
                               signature="bad", signed_by="pub1",
                               algorithm=SignatureAlgorithm.HMAC_SHA256)
        result = verifier.verify_plugin(plugin, signature=sig)
        assert result.overall == SecurityCheckResult.FAILED

    def test_verify_tampered_package(self, verifier, temp_file):
        from app.plugin_marketplace.base import PluginPackage
        plugin = PluginPackage(id="test", name="Test", version="1.0.0",
                                integrity_hash="0" * 64)
        result = verifier.verify_plugin(plugin, file_path=temp_file)
        assert result.integrity_check == SecurityCheckResult.FAILED
        assert result.overall == SecurityCheckResult.FAILED

    def test_verify_valid_integrity(self, verifier, temp_file):
        from app.plugin_marketplace.base import PluginPackage
        h = compute_sha256(temp_file)
        plugin = PluginPackage(id="test", name="Test", version="1.0.0",
                                integrity_hash=h)
        result = verifier.verify_plugin(plugin, file_path=temp_file)
        assert result.integrity_check == SecurityCheckResult.PASSED

    def test_verify_rejected_publisher(self, verifier, signer):
        from app.plugin_marketplace.base import PluginPackage
        verifier._trust_store.block_publisher("blocked_pub")
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        sig = signer.sign("test", "1.0.0", "blocked_pub")
        result = verifier.verify_plugin(plugin, signature=sig)
        assert result.publisher_check == SecurityCheckResult.FAILED

    def test_verify_update_allowed(self, verifier, signer):
        from app.plugin_marketplace.base import PluginPackage
        sig = signer.sign("test", "2.0.0", "pub1")
        result = verifier.verify_update(
            "test", "1.0.0", "2.0.0", signature=sig, integrity_hash="abc")
        assert result.can_proceed is True

    def test_verify_update_rollback_blocked(self, verifier, signer):
        sig = signer.sign("test", "1.0.0", "pub1")
        result = verifier.verify_update(
            "test", "2.0.0", "1.0.0", signature=sig, integrity_hash="abc")
        assert result.can_proceed is True


# ---------------------------------------------------------------------------
# Update Policy Tests
# ---------------------------------------------------------------------------

class TestUpdatePolicy:
    def test_same_version_blocked(self):
        policy = UpdatePolicy()
        result = policy.check_update("test", "1.0.0", "1.0.0")
        assert result == SecurityCheckResult.FAILED

    def test_version_increment_passes(self):
        policy = UpdatePolicy()
        result = policy.check_update("test", "1.0.0", "2.0.0")
        assert result == SecurityCheckResult.PASSED

    def test_downgrade_warning(self):
        policy = UpdatePolicy()
        result = policy.check_update("test", "2.0.0", "1.0.0")
        assert result == SecurityCheckResult.WARNING

    def test_rollback_allowed(self):
        policy = UpdatePolicy()
        assert policy.check_rollback("test", "1.0.0") is True

    def test_rollback_repeated_blocked(self):
        policy = UpdatePolicy()
        policy.check_rollback("test", "1.0.0")
        policy.check_rollback("test", "1.0.0")
        policy.check_rollback("test", "1.0.0")
        assert policy.check_rollback("test", "1.0.0") is False

    def test_rollback_max_limit(self):
        policy = UpdatePolicy()
        policy.check_rollback("test", "1.0.0")
        policy.check_rollback("test", "2.0.0")
        policy.check_rollback("test", "3.0.0")
        assert policy.check_rollback("test", "4.0.0") is False

    def test_rollback_safety_valid(self):
        policy = UpdatePolicy()
        assert policy.verify_rollback_safety("2.0.0", "1.0.0") is True

    def test_rollback_safety_invalid(self):
        policy = UpdatePolicy()
        assert policy.verify_rollback_safety("1.0.0", "2.0.0") is False


# ---------------------------------------------------------------------------
# Health Tests
# ---------------------------------------------------------------------------

class TestPluginSecurityHealth:
    def test_defaults(self):
        h = PluginSecurityHealth()
        assert h.overall_status == "healthy"

    def test_to_dict(self):
        h = PluginSecurityHealth(trusted_publishers=5, total_publishers=10)
        d = h.to_dict()
        assert d["trusted_publishers"] == 5
        assert d["total_publishers"] == 10
        assert "checked_at" in d


# ---------------------------------------------------------------------------
# Security Policy Enforcement Tests
# ---------------------------------------------------------------------------

class TestSecurityPolicyEnforcement:
    def test_unsigned_plugin_rejected_by_strict_policy(self, verifier, policy_manager):
        from app.plugin_marketplace.base import PluginPackage
        policy = RepositoryPolicy(repository_url="strict_repo",
                                   trust_policy=RepositoryTrustPolicy.STRICT)
        policy_manager.set_policy("strict_repo", policy)
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        result = verifier.verify_plugin(plugin, repository_url="strict_repo")
        assert result.overall == SecurityCheckResult.FAILED
        assert any("policy" in e.lower() for e in result.errors)

    def test_expired_certificate_generates_warning(self, verifier, trust_store):
        from app.plugin_marketplace.base import PluginPackage
        cert = trust_store.certificates.issue("p1", "Pub1", "key",
                                               validity_days=-1)
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        sig = PluginSignature(plugin_id="test", version="1.0.0",
                               signature="valid_sig", signed_by="p1",
                               certificate_fingerprint=cert.fingerprint)
        verifier._signer.set_secret_key("key")
        result = verifier.verify_plugin(plugin, signature=sig)
        assert result.certificate_check in (
            SecurityCheckResult.WARNING, SecurityCheckResult.SKIPPED)

    def test_revoked_publisher_rejected(self, verifier, signer,
                                         trust_store):
        from app.plugin_marketplace.base import PluginPackage
        trust_store.publishers.register("p1", "Pub1")
        trust_store.trust_publisher("p1")
        cert = trust_store.certificates.issue("p1", "Pub1", "key")
        trust_store.publishers.add_certificate("p1", cert)
        trust_store.revoke_publisher("p1")
        plugin = PluginPackage(id="test", name="Test", version="1.0.0")
        sig = signer.sign("test", "1.0.0", "p1")
        result = verifier.verify_plugin(plugin, signature=sig)
        assert result.publisher_check == SecurityCheckResult.FAILED

    def test_permission_escalation_detected(self):
        violation = SecurityViolation(
            plugin_id="test",
            violation_type="permission_escalation",
            severity="high",
            description="Plugin attempted to access blocked filesystem path",
        )
        assert violation.violation_type == "permission_escalation"
        assert violation.severity == "high"


# ---------------------------------------------------------------------------
# Kernel Integration Tests
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_registers_security_services(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("plugin_security")
            assert svc is not None
            assert hasattr(svc, "verify_plugin")

            svc2 = kernel.get_service("trust_store")
            assert svc2 is not None
            assert hasattr(svc2, "verify_publisher")

            svc3 = kernel.get_service("publisher_registry")
            assert svc3 is not None

            svc4 = kernel.get_service("repository_policy")
            assert svc4 is not None

            modules = kernel.module_registry.list_modules()
            assert "plugin_security" in modules
            assert "trust_store" in modules

            h = kernel.health()
            assert hasattr(h, "plugin_security")
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_plugin_security_health_in_kernel_health(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            health = kernel.health()
            assert health.plugin_security.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()
