import time
import asyncio
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self._max_requests = max_requests
        self._window = window_seconds
        self._clients: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        async with self._lock:
            timestamps = self._clients[client_ip]
            cutoff = now - self._window
            timestamps[:] = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self._max_requests:
                return Response(
                    status_code=429,
                    content=f'{{"error":{{"code":"RATE_LIMITED","message":"Rate limit exceeded. Try again in {self._window} seconds.","request_id":"","timestamp":{now}}}}}',
                    media_type="application/json",
                    headers={"Retry-After": str(int(self._window))},
                )

            timestamps.append(now)

        return await call_next(request)
