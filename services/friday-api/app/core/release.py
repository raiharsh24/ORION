import os
from datetime import datetime
from pydantic import BaseModel, Field
from app.core.config import settings


BUILD_HASH = os.getenv("BUILD_HASH", "development")
BUILD_COMMIT = os.getenv("BUILD_COMMIT", "HEAD")
BUILD_DATE = os.getenv("BUILD_DATE", datetime.utcnow().isoformat())


class ReleaseInfo(BaseModel):
    version: str = Field(default_factory=lambda: settings.APP_VERSION)
    build_hash: str = Field(default_factory=lambda: BUILD_HASH)
    commit: str = Field(default_factory=lambda: BUILD_COMMIT)
    build_date: str = Field(default_factory=lambda: BUILD_DATE)
    environment: str = Field(default_factory=lambda: settings.ENVIRONMENT)
    python_version: str = Field(default_factory=lambda: _get_python_version())
    debug: bool = Field(default_factory=lambda: settings.DEBUG)


def _get_python_version() -> str:
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_release_info() -> ReleaseInfo:
    return ReleaseInfo()
