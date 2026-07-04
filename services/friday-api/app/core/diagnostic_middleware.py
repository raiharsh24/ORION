import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response




from app.core.diagnostic_request_id import get_or_create_request_id
from app.core.diagnostics import diagnostic_span
from app.kernel.logging_telemetry import FridayTelemetryLogger
from app.core.metrics import get_metrics


class DiagnosticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        headers = dict(request.headers)

        request_id = get_or_create_request_id(
            headers,
            "X-Request-ID",
            "request-id",
        )
        endpoint = request.url.path

        FridayTelemetryLogger.set_trace_context(
            request_id=request_id,
            session_id=headers.get("X-Session-ID") or headers.get("session-id") or None,
            correlation_id=headers.get("X-Correlation-ID") or headers.get("correlation-id") or None,
            mission_id=headers.get("X-Mission-ID") or headers.get("mission-id") or None,
            user_id=headers.get("X-User-ID") or headers.get("user-id") or None,
        )

        # Wrap all non-static endpoints with diagnostics
        if endpoint.startswith("/health") or endpoint.startswith("/kernel") or \
           endpoint.startswith("/missions") or endpoint.startswith("/telemetry") or \
           endpoint.startswith("/workflows") or endpoint.startswith("/chat") or \
           endpoint.startswith("/ask") or endpoint.startswith("/sessions") or \
           endpoint.startswith("/knowledge") or endpoint.startswith("/stream") or \
           endpoint.startswith("/voice") or endpoint.startswith("/vision") or \
           endpoint.startswith("/runtime") or endpoint.startswith("/auth") or \
           endpoint.startswith("/metrics") or endpoint.startswith("/api/"):
            with diagnostic_span(
                request_id=request_id,
                endpoint=endpoint,
                kind="http",
            ):
                start_ms = time.perf_counter() * 1000.0
                resp = await call_next(request)
                elapsed_ms = (time.perf_counter() * 1000.0) - start_ms

                FridayTelemetryLogger.info(
                    module="diagnostics",
                    message=(
                        f"[HTTP] request_id={request_id} endpoint={endpoint} "
                        f"elapsed_ms={elapsed_ms:.2f} status_code={resp.status_code}"
                    ),
                    request_id=request_id,
                    endpoint=endpoint,
                    kind="http",
                    elapsed_ms=elapsed_ms,
                    status_code=resp.status_code,
                )
                resp.headers["X-Request-ID"] = request_id
                # Record metrics
                get_metrics().record_request(endpoint, elapsed_ms, resp.status_code)
                return resp

        # Pass-through for static/docs
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request_id
        return resp

