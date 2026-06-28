from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from app.core.config import settings
from app.core.logger import setup_logger, LoggingMiddleware
from app.core.security import setup_cors
from app.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log startup event
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
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
    # Log shutdown event
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

    # Attach endpoint routes at both root and /api prefix
    # The root level is for direct FastAPI access (e.g., dev, testing)
    app.include_router(api_router)
    # The /api prefix matches the Gateway proxy target paths
    app.include_router(api_router, prefix="/api")

    return app

app = create_app()
