from fastapi import APIRouter
from app.core.metrics import get_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics_endpoint():
    return get_metrics().snapshot()
