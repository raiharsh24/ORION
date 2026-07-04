import os
import time
import hmac
import hashlib
import json
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

AUTH_EXEMPT_PATHS = {"/health", "/live", "/ready", "/version", "/docs", "/openapi.json", "/redoc", "/auth/token", "/metrics"}


def validate_api_key(api_key: str) -> bool:
    master_key = settings.FRIDAY_API_KEY
    if not master_key:
        return False
    return hmac.compare_digest(api_key, master_key)


def compute_api_token(scope: str, expiry: int) -> str:
    payload = {"scope": scope, "expiry": expiry, "ts": int(time.time())}
    data = json.dumps(payload, sort_keys=True)
    return hmac.new(
        settings.FRIDAY_SECRET_KEY.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_api_token(token: str, scope: str) -> bool:
    if not settings.FRIDAY_SECRET_KEY:
        return False
    payload = {"scope": scope, "ts": int(time.time())}
    data = json.dumps(payload, sort_keys=True)
    expected = hmac.new(
        settings.FRIDAY_SECRET_KEY.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(token, expected)


async def get_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[str]:
    if settings.FRIDAY_AUTH_DISABLED:
        return "internal"
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing API key")
    if not validate_api_key(credentials.credentials):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return credentials.credentials


async def optional_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[str]:
    if settings.FRIDAY_AUTH_DISABLED:
        return "internal"
    if credentials is None:
        return None
    if validate_api_key(credentials.credentials):
        return credentials.credentials
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.FRIDAY_AUTH_DISABLED:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(ex) or path == ex for ex in AUTH_EXEMPT_PATHS):
            return await call_next(request)

        api_key = request.headers.get("Authorization", "")
        if api_key.startswith("Bearer "):
            api_key = api_key[7:]
        if not api_key or not validate_api_key(api_key):
            return Response(
                status_code=401,
                content='{"detail":"Missing or invalid API key"}',
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
