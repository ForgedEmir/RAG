"""Router monitoring — /api/monitoring/*"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.auth import require_monitoring
from src.monitoring.tracker import get_stats

monitoring_router = APIRouter()


class ReformulationToggleBody(BaseModel):
    enabled: bool


@monitoring_router.get("/api/monitoring/stats")
async def monitoring_stats(request: Request):
    require_monitoring(request)
    return get_stats()


@monitoring_router.get("/api/monitoring/pipeline")
async def monitoring_pipeline(request: Request):
    require_monitoring(request)
    try:
        from src.search.search import get_pipeline_stats
        stats = get_pipeline_stats()
        try:
            from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
            info = _get_client().get_collection(_COLLECTION_NAME)
            stats["qdrant_vectors"] = info.points_count or 0
            vp = info.config.params.vectors
            if hasattr(vp, "size"):
                stats["qdrant_dimensions"] = vp.size
            elif isinstance(vp, dict):
                first = next(iter(vp.values()), None)
                stats["qdrant_dimensions"] = first.size if first and hasattr(first, "size") else "?"
            else:
                stats["qdrant_dimensions"] = "?"
        except Exception as e:
            stats["qdrant_vectors"] = None
            stats["qdrant_dimensions"] = str(e)[:60]
        return stats
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@monitoring_router.get("/api/monitoring/reformulation")
async def monitoring_reformulation(request: Request):
    require_monitoring(request)
    from src.generation.generator import get_reformulation_enabled
    return {"enabled": get_reformulation_enabled()}


@monitoring_router.post("/api/monitoring/reformulation")
async def monitoring_set_reformulation(body: ReformulationToggleBody, request: Request):
    require_monitoring(request)
    from src.generation.generator import set_reformulation_enabled
    enabled = set_reformulation_enabled(body.enabled)
    return {"ok": True, "enabled": enabled}
