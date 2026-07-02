# Plugin Security Walkthrough

## Overview

Plugin Security provides cryptographic verification, trusted publishers, repository trust policies, secure updates, and rollback protection for the Plugin Marketplace.

## Architecture

```
PluginVerifier
├── PluginSigner        — HMAC-SHA256 signing/verification
├── TrustStore          — Publisher trust and certificate store
│   ├── CertificateManager — Certificate lifecycle (issue, revoke, expire)
│   └── PublisherRegistry  — Publisher trust levels
├── RepositoryPolicyManager — Per-repository trust policies
└── IntegrityVerifier   — SHA-256 file/data integrity checks
```

## Core Concepts

### Plugin Signing
Plugins can be signed using HMAC-SHA256. The signer computes a hash over the plugin payload, and the verifier checks the signature against the stored secret key.

```python
signer = PluginSigner(secret_key="my-secret")
signature = signer.sign("plugin_id", "1.0.0", "publisher_name")
result = signer.verify(signature)  # SecurityCheckResult.PASSED
```

### Certificate Management
Certificates link publishers to cryptographic identities. They have a validity period and can be revoked.

```python
mgr = CertificateManager()
cert = mgr.issue("pub1", "Publisher One", "public_key", validity_days=365)
assert mgr.is_valid(cert.fingerprint)  # True
mgr.revoke(cert.fingerprint, "compromised")
assert mgr.is_valid(cert.fingerprint)  # False
```

### Trust Store
The trust store manages trusted and blocked publishers and their certificates.

```python
store = TrustStore()
store.publishers.register("pub1", "Publisher One")
store.trust_publisher("pub1")
assert store.verify_publisher("pub1") == SecurityCheckResult.PASSED
store.block_publisher("bad_actor")
assert store.verify_publisher("bad_actor") == SecurityCheckResult.FAILED
```

### Repository Trust Policies
Each repository can have a trust policy that controls what is required for installation:

- `STRICT` — requires both signature and integrity hash
- `VERIFIED_ONLY` — requires signature
- `TRUSTED_ONLY` — requires integrity hash
- `PERMISSIVE` — no requirements (fallback to `require_signature`/`require_integrity_hash` flags)

```python
policy_mgr = RepositoryPolicyManager()
policy = RepositoryPolicy(
    repository_url="my_repo",
    trust_policy=RepositoryTrustPolicy.STRICT,
)
policy_mgr.set_policy("my_repo", policy)
```

### Plugin Verification
The `PluginVerifier` orchestrates all checks:

```python
verifier = PluginVerifier(signer, trust_store, policy_mgr, integrity)
result = verifier.verify_plugin(
    plugin=plugin_package,
    signature=signature,
    file_path="/path/to/plugin.zip",
    repository_url="my_repo",
)
if result.passed:
    print("Plugin verified successfully")
else:
    print(f"Verification failed: {result.errors}")
```

### Update Verification
Updates are verified for signature, publisher trust, and rollback safety:

```python
update_result = verifier.verify_update(
    plugin_id="my_plugin",
    from_version="1.0.0",
    to_version="2.0.0",
    signature=signature,
    integrity_hash="abc...",
)
if update_result.can_proceed:
    print("Update is safe to apply")
```

### Rollback Protection
The `UpdatePolicy` prevents repeated rollbacks and detects downgrades:

```python
policy = UpdatePolicy()
policy.check_update("plugin", "1.0.0", "2.0.0")  # PASSED
policy.check_update("plugin", "2.0.0", "1.0.0")  # WARNING (downgrade)
policy.check_rollback("plugin", "1.0.0")  # True
```

## Events

| Event | Trigger |
|---|---|
| `PluginVerified` | Plugin passes all security checks |
| `PluginRejected` | Plugin fails a security check |
| `PublisherTrusted` | Publisher trust level changed to trusted |
| `PublisherRevoked` | Publisher trust was revoked |
| `IntegrityCheckFailed` | File hash mismatch detected |
| `UpdateVerified` | Update passed or failed verification |
| `CertificateExpired` | Publisher certificate expired |
| `SecurityViolationDetected` | A security policy violation occurred |

## Security Checks

The `PluginVerifier` performs these checks in order:

1. **Integrity Check** — SHA-256 hash of plugin file vs. expected hash
2. **Signature Check** — HMAC-SHA256 signature verification
3. **Certificate Check** — Certificate validity, expiration, revocation
4. **Publisher Check** — Publisher trust status and allow/block lists
5. **Repository Check** — Repository trust policy enforcement

## Integration

Registered in kernel boot as Step 7n with 5 DI services:
- `plugin_security` — PluginVerifier instance
- `plugin_signer` — PluginSigner instance
- `trust_store` — TrustStore instance
- `publisher_registry` — PublisherRegistry instance
- `repository_policy` — RepositoryPolicyManager instance

Health is exposed via `KernelHealth.plugin_security` with status `HEALTHY`.
