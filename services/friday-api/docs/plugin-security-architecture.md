# Plugin Security Architecture

## Design Overview

Plugin Security is a lightweight, dependency-free security layer built on Python stdlib cryptography (hashlib, hmac). It wraps the Plugin Marketplace with verification gates for every install, update, and rollback operation.

## Design Principles

1. **No external dependencies** — Uses only Python stdlib (`hashlib`, `hmac`, `json`, `datetime`)
2. **Advisory, not blocking by default** — The verifier reports results; the caller decides whether to enforce
3. **Layered checks** — Each check is independent; failure in one does not skip others (all results reported)
4. **Pluggable policies** — Repository trust policies are configurable per repository URL
5. **Publisher-centric** — Trust is anchored to publisher identities, not plugin IDs

## Module Map

```
app/plugin_security/
├── __init__.py          # Public API exports
├── base.py              # Data models, enums, dataclasses
├── signature.py         # HMAC-SHA256 sign/verify
├── certificate.py       # Certificate lifecycle
├── publisher.py         # Publisher registry
├── trust_store.py       # Combined trust + certificate store
├── integrity.py         # SHA-256 file/data hashing
├── verification.py      # Main plugin verification orchestrator
├── repository_policy.py # Per-repository trust policies
├── update_policy.py     # Update and rollback protection
├── events.py            # Security event types
└── health.py            # PluginSecurityHealth model
```

## Data Flow

```
Plugin Install Request
        │
        ▼
PluginVerifier.verify_plugin()
        │
        ├── IntegrityVerifier.verify_file() → SHA-256 match?
        ├── PluginSigner.verify() → HMAC signature valid?
        ├── TrustStore.verify_certificate() → Cert valid/expired/revoked?
        ├── TrustStore.verify_publisher() → Publisher trusted/blocked?
        └── RepositoryPolicyManager.check_repository_trust() → Policy allows?
        │
        ▼
SecurityVerificationResult
    ├── overall: PASSED / FAILED / WARNING / SKIPPED
    ├── errors: [...]     (blocking issues)
    └── warnings: [...]   (non-blocking issues)
```

## Key Models

### SecurityCheckResult
- `PASSED` — Check completed successfully
- `FAILED` — Check detected a violation
- `SKIPPED` — Check was not applicable (no signature, no cert, etc.)
- `WARNING` — Check passed but has concerns (expired cert, downgrade)

### RepositoryTrustPolicy
- **STRICT**: Both signature AND integrity hash required
- **VERIFIED_ONLY**: Signature required (integrity optional)
- **TRUSTED_ONLY**: Integrity hash required (signature optional)
- **PERMISSIVE**: No policy-level requirements; falls back to individual flags

### Publisher Trust Levels
- `UNTRUSTED` — Default; no trust granted
- `LOW` — Minimal trust
- `MEDIUM` — Moderate trust
- `HIGH` — High trust
- `VERIFIED` — Fully verified publisher

## Security Considerations

1. **HMAC vs Asymmetric**: Current implementation uses HMAC-SHA256 (symmetric). RSA/ECDSA support is defined in `SignatureAlgorithm` enum but not yet implemented.
2. **Key Management**: The secret key is configured at startup. Production should load from a secure vault or environment, not configuration.
3. **Certificate Chain**: Only single certificates are supported. Chain-of-trust (CA) is not implemented.
4. **Revocation**: Revocation is by publisher identity, not by certificate serial number. A publisher can hold multiple certificates; revoking the publisher revokes trust for all their certificates.

## Integration Points

| Integration | File | Pattern |
|---|---|---|
| DI Registration | `boot.py:490` (Step 7n) | `register_singleton` + `register_module` |
| Health Check | `kernel.py:health()` | `check_service_health("plugin_security", ...)` |
| Health Model | `health.py:KernelHealth` | `plugin_security: SubsystemHealth` field |
| Capability | `boot.py` | `register_capability("PluginSecurity", ...)` |
| Events | `events.py` | 8 event types extending `FridayEvent` |

## Event Types

| Event | Payload | When |
|---|---|---|
| PluginVerified | plugin_id, version, passed, errors | After verification completes |
| PluginRejected | plugin_id, version, reason, details | When verification fails |
| PublisherTrusted | publisher_id, name, trust_level | Publisher trust granted |
| PublisherRevoked | publisher_id, name, reason | Publisher trust revoked |
| IntegrityCheckFailed | plugin_id, version, expected_hash, actual_hash | Hash mismatch detected |
| UpdateVerified | plugin_id, from_version, to_version, passed | Update checked |
| CertificateExpired | publisher_id, fingerprint, expired_at | Cert past expiry |
| SecurityViolationDetected | plugin_id, violation_type, severity, description | Policy violated |

## Health Model

```python
@dataclass
class PluginSecurityHealth:
    overall_status: str           # "healthy" / "warning" / "error"
    trusted_publishers: int
    revoked_publishers: int
    total_certificates: int
    total_publishers: int
    blocked_publishers: int
    failed_verifications: int
    tampered_packages: int
    repository_policies: int
    repository_trust_state: str
    signature_algorithm: str
    last_verification: Optional[str]
    violations: List[Dict[str, Any]]
    checked_at: Optional[datetime]
```

## Dependencies

- **Runtime**: Python 3.12+ stdlib only (hashlib, hmac, json, datetime)
- **Test**: pytest, anyio (for async kernel boot tests)
- **External**: None
