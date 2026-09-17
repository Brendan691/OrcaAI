"""联网搜索 API"""
from fastapi import APIRouter

from ..services.search_service import search_service

router = APIRouter(prefix="/api/search/internet", tags=["联网搜索"])


@router.get("/")
async def search_internet(q: str = "", num: int = 5):
    """联网搜索"""
    if not q:
        return {"results": [], "total": 0}
    outcome = await search_service.search(q, num)
    return {
        "results": [result.model_dump() for result in outcome.results],
        "total": len(outcome.results),
        "status": outcome.status,
        "provider": outcome.provider,
        "warnings": [warning.model_dump() for warning in outcome.warnings],
    }
