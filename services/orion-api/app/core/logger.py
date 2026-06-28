import sys
import time
import uuid
from loguru import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.kernel.logging_telemetry import OrionTelemetryLogger

def setup_logger() -> None:
    # Clear default logger handlers
    logger.remove()
    
    # Custom colored format for logging stdout (binds extra fields if present)
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level> "
        "<cyan>[req_id={extra[request_id]} correlation_id={extra[correlation_id]}]</cyan>"
    )
    
    # Loguru filter/format to avoid KeyErrors when extra fields are missing
    def patch_record(record):
        extra = record["extra"]
        if "request_id" not in extra or extra["request_id"] is None:
            extra["request_id"] = "-"
        if "correlation_id" not in extra or extra["correlation_id"] is None:
            extra["correlation_id"] = "-"
        return True

    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG",
        filter=patch_record,
        enqueue=True
    )

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Resolve or generate tracking IDs
        request_id = request.headers.get("X-Request-ID") or request.headers.get("request-id") or str(uuid.uuid4())
        session_id = request.headers.get("X-Session-ID") or request.headers.get("session-id") or str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("correlation-id") or str(uuid.uuid4())
        
        # Populate context variables
        OrionTelemetryLogger.set_trace_context(
            request_id=request_id,
            session_id=session_id,
            correlation_id=correlation_id
        )
        
        OrionTelemetryLogger.info(
            module="http_gateway",
            message=f"Incoming request: {method} {path}"
        )
        
        try:
            response = await call_next(request)
            
            # Propagate back to headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Session-ID"] = session_id
            response.headers["X-Correlation-ID"] = correlation_id
            
            latency = (time.time() - start_time) * 1000
            OrionTelemetryLogger.info(
                module="http_gateway",
                message=f"Request complete: {method} {path} - Status: {response.status_code} - Latency: {latency:.2f}ms",
                status_code=response.status_code,
                latency_ms=latency
            )
            return response
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            OrionTelemetryLogger.error(
                module="http_gateway",
                message=f"Request failed: {method} {path} - Exception: {type(e).__name__}: {str(e)} - Latency: {latency:.2f}ms",
                exception_type=type(e).__name__,
                exception_msg=str(e),
                latency_ms=latency
            )
            raise e
        finally:
            OrionTelemetryLogger.clear_context()
