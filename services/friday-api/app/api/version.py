from fastapi import APIRouter
from app.core.release import get_release_info

router = APIRouter(tags=["version"])


@router.get("/version")
async def version_endpoint():
    """Returns release metadata: version, build hash, commit, build date, environment."""
    return get_release_info().model_dump()
