from fastapi import APIRouter

from app.services.metrics_service import compute_dashboard_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics/dashboard")
async def metrics_dashboard() -> dict:
    """요약 + 프로젝트별 모듈·Severity + 전역 모듈 합산 (한 번에)."""
    return await compute_dashboard_metrics()


@router.get("/metrics/summary")
async def metrics_summary() -> dict:
    data = await compute_dashboard_metrics()
    return data["summary"]


@router.get("/metrics/modules")
async def metrics_modules() -> dict:
    data = await compute_dashboard_metrics()
    return {
        "byProject": data["byProject"],
        "globalModules": data["globalModules"],
        "errors": data["errors"],
    }
