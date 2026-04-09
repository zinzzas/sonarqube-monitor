from typing import Any

from fastapi import APIRouter, Request

from app.services.issue_snapshot_query import (
    strip_internal_query_params,
    try_issue_search_from_snapshot,
)
from app.services.module_issue_exclude import filter_normalized_proxy_issues_page
from app.services.sonar_api import collect_issues_search_params, proxy_issues_search

router = APIRouter(tags=["issues"])


def _enrich_issue_component_strings(issues: list[Any]) -> None:
    """일부 Sonar 응답은 `component` 대신 `mainComponent.key`·`componentKey`만 준다."""
    for issue in issues:
        if not isinstance(issue, dict) or issue.get("component"):
            continue
        main = issue.get("mainComponent")
        if isinstance(main, dict):
            mk = main.get("key")
            if isinstance(mk, str) and mk.strip():
                issue["component"] = mk.strip()
                continue
        ck = issue.get("componentKey")
        if isinstance(ck, str) and ck.strip():
            issue["component"] = ck.strip()


def _coerce_issues_list(raw: Any) -> list[Any]:
    """Sonar는 보통 issues 배열을 주지만, 일부 응답·직렬화에서 dict 등으로 올 수 있다."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return list(raw.values())
    return []


def _normalize_sonar_issues_search(data: dict[str, Any]) -> dict[str, Any]:
    """
    SonarQube 버전에 따라 `total`이 최상위가 아니라 `paging.total`에만 오는 경우가 많다.
    프론트가 `data.total`·`data.issues`만 보도록 맞춘다.
    """
    out = dict(data)
    paging = out.get("paging")
    if isinstance(paging, dict) and "total" not in out and isinstance(paging.get("total"), int):
        out["total"] = paging["total"]
    raw_issues = out.get("issues")
    if raw_issues is None and isinstance(out.get("Issues"), list):
        raw_issues = out.get("Issues")
    out["issues"] = _coerce_issues_list(raw_issues)
    if isinstance(out["issues"], list):
        _enrich_issue_component_strings(out["issues"])
    return out


@router.get("/issues/search")
async def issues_search(request: Request) -> dict:
    """
    이슈 검색: 스냅샷(대시보드 집계와 동일 `issues_full`)이 있으면 로컬 필터·페이징.
    없거나 미지원이면 Sonar `GET /api/issues/search` 프록시.
    `?source=live` 는 항상 Sonar. 내부 파라미터 `source` 는 업스트림에 전달하지 않음.
    """
    params = collect_issues_search_params(request)
    local = try_issue_search_from_snapshot(params)
    if local is not None:
        return _normalize_sonar_issues_search(local)
    upstream = strip_internal_query_params(params)
    raw = await proxy_issues_search(upstream)
    if isinstance(raw, dict):
        out = _normalize_sonar_issues_search(raw)
        return filter_normalized_proxy_issues_page(out, upstream)
    return raw
