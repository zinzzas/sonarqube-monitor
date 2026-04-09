"""
대시보드 집계와 동일한 `module_segment_labels.maps.<profile>.exclude` 규칙으로 이슈 행을 걸러낸다.

- 스냅샷 기반 issues/search: 전량 필터 후 페이징 → total 정합.
- Sonar 프록시(live): **현재 페이지** 이슈만 필터. 업스트림 `total`은 Sonar 기준이라
  제외 경로가 다른 페이지에만 있으면 숫자와 목록이 완전히 일치하지 않을 수 있음(한계).
"""
from __future__ import annotations

from typing import Any

from app.config.load_projects import project_row_by_component_key
from app.core.module_extract import is_excluded_from_module_rollup
from app.core.team_high_risk import issue_component_key


def _pairs_last_wins(pairs: list[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in pairs:
        out[k] = v
    return out


def project_id_for_single_component_issues_query(
    pairs: list[tuple[str, str]],
) -> str | None:
    """
    `componentKeys` 가 정확히 하나이고 `component_projects.json` 에 매핑될 때만 project id.
    다중 키·미등록이면 None (exclude 일괄 적용 생략).
    """
    d = _pairs_last_wins(pairs)
    raw = (d.get("componentKeys") or "").strip()
    if not raw or "," in raw:
        return None
    row = project_row_by_component_key(raw)
    if row is None:
        return None
    pid = str(row.get("id") or "").strip()
    return pid or None


def filter_issue_dicts_by_module_exclude(
    issues: list[dict[str, Any]],
    project_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    제외 대상 이슈를 빼고 (남은 목록, 제거 건수) 반환.
    component 키가 비어 있으면 제외 판정에서 제외(집계와 동일하게 빈 키는 exclude False).
    """
    if not project_id or not issues:
        return [i for i in issues if isinstance(i, dict)], 0
    out: list[dict[str, Any]] = []
    removed = 0
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        comp = issue_component_key(issue)
        if is_excluded_from_module_rollup(comp, project_id):
            removed += 1
            continue
        out.append(issue)
    return out, removed


def filter_normalized_proxy_issues_page(
    data: dict[str, Any],
    pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    """
    Sonar 프록시 응답: **현재 페이지** `issues` 만 집계 규칙에 맞게 제거.
    `total` / `paging.total` 은 Sonar 원본 유지(다른 페이지에 제외 대상이 더 있을 수 있음).
    """
    pid = project_id_for_single_component_issues_query(pairs)
    if not pid:
        return data
    issues = data.get("issues")
    if not isinstance(issues, list):
        return data
    dicts = [x for x in issues if isinstance(x, dict)]
    kept, removed = filter_issue_dicts_by_module_exclude(dicts, pid)
    if removed == 0:
        return data
    out = dict(data)
    out["issues"] = kept
    return out
