import time
import traceback
from typing import Optional, Any, Dict
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from app.kernel.logging_telemetry import FridayTelemetryLogger


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class ErrorResponse(BaseModel):
    error: ErrorDetail


def build_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    ctx = FridayTelemetryLogger.get_trace_context()
    error = ErrorDetail(
        code=code,
        message=message,
        details=details,
        request_id=request_id or ctx.get("request_id"),
        timestamp=time.time(),
    )
    return JSONResponse(
        status_code=status_code,
        content={"error": error.model_dump()},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    ctx = FridayTelemetryLogger.get_trace_context()
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return build_error_response(
        code=code,
        message=str(exc.detail) if exc.detail else "An error occurred",
        status_code=exc.status_code,
        request_id=ctx.get("request_id"),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    ctx = FridayTelemetryLogger.get_trace_context()
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return build_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=422,
        details={"errors": errors},
        request_id=ctx.get("request_id"),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    ctx = FridayTelemetryLogger.get_trace_context()
    logger.error(
        "Unhandled exception: {exc_type}: {exc_msg}",
        exc_type=type(exc).__name__,
        exc_msg=str(exc),
    )
    logger.debug(traceback.format_exc())
    return build_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        status_code=500,
        request_id=ctx.get("request_id"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
