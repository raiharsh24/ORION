import sys
import time
from loguru import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

def setup_logger() -> None:
    # Clear default logger handlers
    logger.remove()
    
    # Custom colored format for logging stdout
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG",
        enqueue=True
    )

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        logger.info(f"Incoming request: {method} {path}")
        
        try:
            response = await call_next(request)
            latency = (time.time() - start_time) * 1000
            logger.info(
                f"Request complete: {method} {path} - Status: {response.status_code} - Latency: {latency:.2f}ms"
            )
            return response
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {method} {path} - Exception: {type(e).__name__}: {str(e)} - Latency: {latency:.2f}ms"
            )
            raise e
