from fastapi import APIRouter, Query

from app.services.metrics_service import compute_dashboard_metrics, export_flat_issues_json

router = APIRouter(tags=["metrics"])


@router.get("/metrics/dashboard")
async def metrics_dashboard(
    project_id: str | None = Query(
        None,
        alias="projectId",
        description="집계 대상 프로젝트 id. `all` 이면 전 프로젝트·OPEN·BLOCKER/HIGH/MEDIUM만 병합.",
    ),
) -> dict:
    """요약 + byProject. 단일 id는 전 심각도, `all`은 B·H·M만 순차 수집 후 병합."""
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
