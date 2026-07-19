# Known Issues

Active bugs, faked components, and test regressions that require resolution:

---

## 1. System Python Alembic Shadowing
- **Impact**: Minor / Environment dependent.
- **Description**: Running python commands with system python (which lacks the `alembic` package) will succeed to `import alembic` because of Python 3 namespace package matching on the local `services/friday-api/alembic` migration directory. However, `from alembic.config import Config` will fail with `ModuleNotFoundError`.
- **Remediation Plan**: Always use the project's virtualenv interpreter (`.venv/bin/python3`). A robust import fallback is now implemented in `migrate.py` to manually initialize SQLite schemas when the `alembic` package is not available.

---

## 2. Deprecation Warnings
- **Impact**: Non-blocking warning logs.
- **Description**: Standard `datetime.datetime.utcnow()` deprecation warnings in SQLAlchemy and model serializers.
- **Remediation Plan**: Update references to `datetime.datetime.now(datetime.UTC)`.

