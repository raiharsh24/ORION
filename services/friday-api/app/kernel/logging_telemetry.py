import contextvars
import time
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager
from loguru import logger

# Context variables to preserve request and tracking IDs across async context boundaries
request_id_var = contextvars.ContextVar("request_id", default=None)
session_id_var = contextvars.ContextVar("session_id", default=None)
correlation_id_var = contextvars.ContextVar("correlation_id", default=None)
mission_id_var = contextvars.ContextVar("mission_id", default=None)
user_id_var = contextvars.ContextVar("user_id", default=None)

class FridayTelemetryLogger:
    """
    Structured Logging & Telemetry utility binding context tracing IDs and measuring
    subsystem execution latency.
    """
    @staticmethod
    def set_trace_context(
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Sets tracking correlation context values."""
        if request_id:
            request_id_var.set(request_id)
        if session_id:
            session_id_var.set(session_id)
        if correlation_id:
            correlation_id_var.set(correlation_id)
        if mission_id:
            mission_id_var.set(mission_id)
        if user_id:
            user_id_var.set(user_id)

    @staticmethod
    def get_trace_context() -> Dict[str, Optional[str]]:
        """Retrieves tracking correlation context values."""
        return {
            "request_id": request_id_var.get(),
            "session_id": session_id_var.get(),
            "correlation_id": correlation_id_var.get(),
            "mission_id": mission_id_var.get(),
            "user_id": user_id_var.get(),
        }

    @staticmethod
    def clear_context() -> None:
        """Clears tracing context values."""
        request_id_var.set(None)
        session_id_var.set(None)
        correlation_id_var.set(None)
        mission_id_var.set(None)
        user_id_var.set(None)

    @staticmethod
    def log(level: str, module: str, message: str, **kwargs: Any) -> None:
        """Binds context IDs and logs a message using Loguru."""
        context = FridayTelemetryLogger.get_trace_context()
        log_data = {
            "module_name": module,
            "request_id": context["request_id"],
            "session_id": context["session_id"],
            "correlation_id": context["correlation_id"],
            "mission_id": context["mission_id"],
            "user_id": context["user_id"],
            **kwargs
        }
        logger.bind(**log_data).log(level.upper(), message)

    @staticmethod
    def info(module: str, message: str, **kwargs: Any) -> None:
        FridayTelemetryLogger.log("INFO", module, message, **kwargs)

    @staticmethod
    def debug(module: str, message: str, **kwargs: Any) -> None:
        FridayTelemetryLogger.log("DEBUG", module, message, **kwargs)

    @staticmethod
    def warning(module: str, message: str, **kwargs: Any) -> None:
        FridayTelemetryLogger.log("WARNING", module, message, **kwargs)

    @staticmethod
    def error(module: str, message: str, **kwargs: Any) -> None:
        FridayTelemetryLogger.log("ERROR", module, message, **kwargs)

    @staticmethod
    @contextmanager
    def measure_performance(module: str, operation: str) -> Generator[None, None, None]:
        """Tracks the performance latency of code execution blocks."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            FridayTelemetryLogger.info(
                module=module,
                message=f"Performance: '{operation}' executed in {duration_ms:.2f}ms",
                metric_name=operation,
                duration_ms=duration_ms
            )
