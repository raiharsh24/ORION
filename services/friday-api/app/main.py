from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from app.core.config import settings
from app.core.logger import setup_logger, LoggingMiddleware
from app.core.security import setup_cors
from app.api import api_router
from app.core.config_profiles import get_profile_defaults

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply environment-specific profile defaults
    profile = get_profile_defaults(settings.ENVIRONMENT)
    for key, value in profile.items():
        if hasattr(settings, key):
            current = getattr(settings, key)
            if not current and key in ("FRIDAY_API_KEY", "FRIDAY_SECRET_KEY"):
                setattr(settings, key, value)
            elif key in ("RATE_LIMIT_ENABLED", "RATE_LIMIT_MAX", "RATE_LIMIT_WINDOW"):
                if not hasattr(settings, "_profile_applied"):
                    setattr(settings, key, value)

    # Log startup event
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]...")
    logger.info(f"Debug mode: {settings.DEBUG}, Auth: {'disabled' if settings.FRIDAY_AUTH_DISABLED else 'enabled'}")
    
    from app.kernel.kernel import FridayKernel
    from app.kernel.state import KernelState
    from app.missions.mission_manager import CreateMissionRequest
    
    kernel = FridayKernel.get_instance()
    if kernel.state() == KernelState.STOPPED:
        await kernel.boot()
        
    mission_manager = kernel.get_service("mission_engine")
    if mission_manager:
        existing = await mission_manager.list_missions()
        if not existing:
            await mission_manager.create_mission(
                CreateMissionRequest(
                    name="Verify API Compilation",
                    description="Run compilation check across all backend modules",
                    priority="HIGH",
                    type="SYSTEM",
                    metadata={
                        "steps": ["Init", "Load Config", "Compile Registry", "Compile Main", "Test Baseline"],
                        "workflowName": "api_compile_check",
                        "current_tool": "filesystem.read_file",
                    }
                )
            )
            await mission_manager.create_mission(
                CreateMissionRequest(
                    name="Sync Vector DB",
                    description="Upload local files and chunks to ChromaDB",
                    priority="NORMAL",
                    type="KNOWLEDGE",
                    metadata={
                        "steps": ["Init", "Chunk Documents", "Generate Embeddings", "Upsert Chroma", "Verify Index"],
                        "workflowName": "sync_vector_db",
                    }
                )
            )
            await mission_manager.create_mission(
                CreateMissionRequest(
                    name="Host Web App Gateway",
                    description="Deploy API server on host uvicorn gateway",
                    priority="CRITICAL",
                    type="SYSTEM",
                    metadata={
                        "steps": ["Init", "Verify Env", "Launch Uvicorn", "Ping Gateway", "Verify Health"],
                        "workflowName": "launch_gateway",
                        "current_tool": "terminal.run_command",
                    }
                )
            )
            logger.info("Baseline missions pre-populated successfully in MissionManager.")
            
    yield
    # Graceful shutdown with active connection draining
    from app.core.shutdown import graceful_shutdown
    event_bus = kernel.get_service("event_bus") if kernel else None
    await graceful_shutdown(kernel, event_bus, timeout=30.0)
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await kernel.shutdown()

def create_app() -> FastAPI:
    # Setup loguru format first
    setup_logger()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan
    )

    # Attach middlewares
    setup_cors(app)
    app.add_middleware(LoggingMiddleware)

    # Rate limiter middleware (optional)
    if settings.RATE_LIMIT_ENABLED:
        from app.core.rate_limiter import RateLimitMiddleware
        app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_MAX, window_seconds=settings.RATE_LIMIT_WINDOW)

    # Temporary diagnostics-only middleware (no behavior change)
    from app.core.diagnostic_middleware import DiagnosticMiddleware
    app.add_middleware(DiagnosticMiddleware)

    # Auth middleware (skipped when FRIDAY_AUTH_DISABLED=True)
    if not settings.FRIDAY_AUTH_DISABLED:
        from app.core.auth import AuthMiddleware
        app.add_middleware(AuthMiddleware)

    # Register global error handlers
    from app.core.error_handler import register_error_handlers
    register_error_handlers(app)

    # Attach endpoint routes at both root and /api prefix
    # The root level is for direct FastAPI access (e.g., dev, testing)
    app.include_router(api_router)
    # The /api prefix matches the Gateway proxy target paths
    app.include_router(api_router, prefix="/api")
    # Auth routes (exempt from auth middleware)
    from app.api.auth import router as auth_router
    app.include_router(auth_router)
    # Metrics endpoint (exempt from auth)
    from app.api.metrics import router as metrics_router
    app.include_router(metrics_router)

    return app

app = create_app()
