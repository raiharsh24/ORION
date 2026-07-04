import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.kernel.logging_telemetry import FridayTelemetryLogger


@dataclass
class DiagnosticEvent:
    request_id: str
    endpoint: str
    kind: str
    start_ms: float
    success: Optional[bool] = None
    exception_type: Optional[str] = None
    exception_msg: Optional[str] = None
    timeout_source: Optional[str] = None
    elapsed_ms: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None


def new_request_id() -> str:
    return str(uuid.uuid4())


def get_timeout_source_from_exception(exc: BaseException) -> Optional[str]:
    msg = str(exc).lower()
    t = type(exc).__name__.lower()
    if "timeout" in msg or "timed out" in msg or "deadline" in msg:
        return f"{type(exc).__name__}: {str(exc)}"
    if "connect" in msg and "timeout" in msg:
        return f"{type(exc).__name__}: {str(exc)}"
    return None


@contextmanager
def diagnostic_span(
    *,
    request_id: str,
    endpoint: str,
    kind: str,
    extra: Optional[Dict[str, Any]] = None,
    fail_log_level: str = "ERROR",
):
    start = time.perf_counter()
    try:
        FridayTelemetryLogger.info(
            module="diagnostics",
            message=f"[BEGIN] request_id={request_id} endpoint={endpoint} kind={kind}",
            request_id=request_id,
            endpoint=endpoint,
            kind=kind,
        )
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        FridayTelemetryLogger.info(
            module="diagnostics",
            message=f"[END] request_id={request_id} endpoint={endpoint} kind={kind} success=true elapsed_ms={elapsed_ms:.2f}",
            request_id=request_id,
            endpoint=endpoint,
            kind=kind,
            success=True,
            elapsed_ms=elapsed_ms,
            **(extra or {}),
        )
    except BaseException as e:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        timeout_source = get_timeout_source_from_exception(e)
        FridayTelemetryLogger.info(
            module="diagnostics",
            message=f"[END] request_id={request_id} endpoint={endpoint} kind={kind} success=false elapsed_ms={elapsed_ms:.2f} exc={type(e).__name__}:{e} timeout_source={timeout_source}",
            request_id=request_id,
            endpoint=endpoint,
            kind=kind,
            success=False,
            elapsed_ms=elapsed_ms,
            exception_type=type(e).__name__,
            exception_msg=str(e),
            timeout_source=timeout_source,
            **(extra or {}),
        )
        raise e

