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
from app.api.workflow_runtime import router as workflow_runtime_router
from app.api.vision_routes import router as vision_router
from app.api.runtime_missions import router as runtime_missions_router
from app.api.metrics import router as metrics_router
from app.api.readiness import router as readiness_router
from app.api.version import router as version_router
from app.api.memory_inspector import router as memory_inspector_router
from app.api.planner_inspector import router as planner_inspector_router
from app.api.runtime_inspector import router as runtime_inspector_router
from app.api.agent_inspector import router as agent_inspector_router
from app.api.cognitive_inspector import router as cognitive_inspector_router
from app.api.atlas import router as atlas_router
from app.api.tools import router as tools_router

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
api_router.include_router(workflow_runtime_router)
api_router.include_router(vision_router)
api_router.include_router(runtime_missions_router)
api_router.include_router(metrics_router)
api_router.include_router(readiness_router)
api_router.include_router(version_router)
api_router.include_router(memory_inspector_router)
api_router.include_router(planner_inspector_router)
api_router.include_router(runtime_inspector_router)
api_router.include_router(agent_inspector_router)
api_router.include_router(cognitive_inspector_router)
api_router.include_router(atlas_router)
api_router.include_router(tools_router)
