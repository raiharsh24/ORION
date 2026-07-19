# Known Issues

Active bugs, faked components, and test regressions that require resolution:

---

## 1. Legacy Connectivity Test Failure
- **Test File**: [tests/test_v0_4.py](file:///home/warlock/Downloads/projects/ORION/services/friday-api/tests/test_v0_4.py)
- **Test Case**: `test_ask_endpoint_success`
- **Error message**: `assert 0 > 0`
- **Impact**: Non-blocking. The test asserts placeholder values and does not verify real operational components.
- **Remediation Plan**: Refactor or clean up the legacy endpoint mock assertions.

---

## 2. Deprecation Warnings
- **Impact**: Non-blocking warning logs.
- **Description**: Standard `datetime.datetime.utcnow()` deprecation warnings in SQLAlchemy and model serializers.
- **Remediation Plan**: Update references to `datetime.datetime.now(datetime.UTC)`.
