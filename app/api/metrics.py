from fastapi import APIRouter, Query

from app.services.metrics_service import compute_dashboard_metrics, export_flat_issues_json

router = APIRouter(tags=["metrics"])


@router.get("/metrics/dashboard")
async def metrics_dashboard(
    project_id: str | None = Query(None, alias="projectId", description="집계 대상 프로젝트 id"),
) -> dict:
    """요약 + 선택 프로젝트 모듈·Severity (Sonar 호출은 해당 프로젝트만 순차)."""
    return await compute_dashboard_metrics(project_id=project_id)


@router.get("/metrics/summary")
async def metrics_summary(
    project_id: str | None = Query(None, alias="projectId"),
) -> dict:
    data = await compute_dashboard_metrics(project_id=project_id)
    return data["summary"]


@router.get("/metrics/modules")
async def metrics_modules(
    project_id: str | None = Query(None, alias="projectId"),
) -> dict:
    data = await compute_dashboard_metrics(project_id=project_id)
    return {
        "byProject": data["byProject"],
        "globalModules": data["globalModules"],
        "errors": data["errors"],
    }


@router.get("/metrics/export/issues")
async def metrics_export_issues() -> dict:
    """집계와 동일 OPEN 이슈를 이슈 단위로 펼친 목록(component·line 포함)."""
    return await export_flat_issues_json()
