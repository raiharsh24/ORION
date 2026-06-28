from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.routes import router as prompt_router
from app.api.sessions import router as sessions_router
from app.api.knowledge import router as knowledge_router
from app.api.kernel import router as kernel_router
from app.api.missions import router as missions_router
from app.api.stream import router as stream_router
from app.api.workflows import router as workflows_router
from app.api.voice import router as voice_router

api_router = APIRouter()

# Register sub-routers directly to the base path
api_router.include_router(health_router)
api_router.include_router(prompt_router)
api_router.include_router(sessions_router)
api_router.include_router(knowledge_router)
api_router.include_router(kernel_router)
api_router.include_router(missions_router)
api_router.include_router(stream_router)
api_router.include_router(workflows_router)
api_router.include_router(voice_router)
