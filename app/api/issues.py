from fastapi import APIRouter, Request

from app.services.sonar_api import collect_issues_search_params, proxy_issues_search

router = APIRouter(tags=["issues"])


@router.get("/issues/search")
async def issues_search(request: Request) -> dict:
    """
    SonarQube `GET /api/issues/search` 프록시.
    쿼리스트링 전달; `componentKeys` 없으면 `SONAR_SAMPLE_COMPONENT_KEYS` 사용.
    """
    params = collect_issues_search_params(request)
    return await proxy_issues_search(params)
