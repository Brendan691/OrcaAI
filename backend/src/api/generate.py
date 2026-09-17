"""AI 内容生成 API — 航运周报 / 风险预警 / 公约解读"""
from fastapi import APIRouter, HTTPException

from ..models.document import ReportGenerateRequest, ReportGenerateResponse
from ..services.report_generator import report_generator

router = APIRouter(prefix="/api/generate", tags=["AI 内容生成"])


@router.post("/report", response_model=ReportGenerateResponse)
async def generate_report(req: ReportGenerateRequest):
    result = await report_generator.generate(
        req.report_type,
        req.time_range or "week",
        req.search_internet
    )
    if not result["success"]:
        raise HTTPException(400, result["content"])
    return ReportGenerateResponse(**result)


@router.get("/report-types")
async def list_report_types():
    return {
        "types": [
            {"id": k, "name": v["name"]}
            for k, v in report_generator.REPORT_TYPES.items()
        ]
    }
