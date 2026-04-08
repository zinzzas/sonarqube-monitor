"""
Sonar `issues/search` 와 동일한 쿼리스트링을 스냅샷(`issues_full.json`)에 적용.

- `component_projects.json` 의 단일 componentKey 와 매칭될 때만 사용.
- `teamId` 가 있으면 `team_id_for_issue_row`(웹 `teamIdForIssue` 와 동일) 로 필터 후 정렬·페이징.
- 스냅샷이 없거나 TTL 만료·`severityFloor` 불일치(설정 변경)·미지원 정렬이면 None → Sonar 프록시.
"""
from __future__ import annotations

import time
from typing import Any

from app.config.load_projects import project_row_by_component_key, severity_floor_for_full_metrics
from app.core.config import settings
from app.core.severity import (
    STANDARD_SEVERITIES,
    normalize_from_sonar,
    severity_bucket_for_issue,
    severity_rank_for_sort,
)
from app.core.team_high_risk import team_id_for_issue_row
from app.services import issue_snapshot_store


def _pairs_last_wins(pairs: list[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in pairs:
        out[k] = v
    return out


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def _creation_sort_key(issue: dict[str, Any]) -> str:
    s = issue.get("creationDate") or issue.get("updateDate") or ""
    return str(s) if s else ""


def _issue_key_sort(issue: dict[str, Any]) -> str:
    k = issue.get("key") or issue.get("issueKey") or ""
    return str(k)


def _allowed_severity_standards(severities_param: str | None) -> set[str] | None:
    """None 이면 심각도 필터 없음(전체)."""
    if severities_param is None or not str(severities_param).strip():
        return None
    out: set[str] = set()
    for tok in str(severities_param).split(","):
        u = tok.strip().upper()
        if not u:
            continue
        std = normalize_from_sonar(u)
        if std in STANDARD_SEVERITIES:
            out.add(std)
    return out if out else None


def _allowed_statuses(statuses_param: str | None) -> set[str]:
    if statuses_param is None or not str(statuses_param).strip():
        return {"OPEN"}
    return {s.strip().upper() for s in str(statuses_param).split(",") if s.strip()}


def _author_matches(issue: dict[str, Any], authors_param: str | None) -> bool:
    if authors_param is None or not str(authors_param).strip():
        return True
    want = [a.strip().lower() for a in str(authors_param).split(",") if a.strip()]
    if not want:
        return True
    auth = issue.get("author") or issue.get("assignee") or ""
    if isinstance(auth, dict):
        auth = auth.get("login") or auth.get("name") or ""
    a = str(auth).strip().lower()
    if not a:
        return False
    return any(w in a or a == w for w in want)


def _filter_issues(
    issues: list[dict[str, Any]],
    *,
    severities_param: str | None,
    statuses_param: str | None,
    authors_param: str | None,
) -> list[dict[str, Any]]:
    sev_allow = _allowed_severity_standards(severities_param)
    st_allow = _allowed_statuses(statuses_param)
    out: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        st = str(issue.get("status") or "").strip().upper()
        if st_allow and st not in st_allow:
            continue
        if sev_allow is not None:
            bucket = severity_bucket_for_issue(issue)
            if bucket not in sev_allow:
                continue
        if not _author_matches(issue, authors_param):
            continue
        out.append(issue)
    return out


def _sort_issues(
    issues: list[dict[str, Any]],
    *,
    sort_field: str | None,
    asc: bool | None,
) -> list[dict[str, Any]]:
    """sort_field: SEVERITY | CREATION_DATE; asc None 은 false 와 동일(Sonar 기본 desc)."""
    sf = (sort_field or "").strip().upper()
    ascending = asc is True
    keyed: list[tuple[Any, ...] | dict[str, Any]] = []
    if sf == "SEVERITY":
        for i in issues:
            r = severity_rank_for_sort(i)
            keyed.append((r, _issue_key_sort(i), i))
        keyed.sort(key=lambda t: (t[0], t[1]), reverse=not ascending)
        return [t[2] for t in keyed]  # type: ignore[misc]
    if sf == "CREATION_DATE":
        for i in issues:
            keyed.append((_creation_sort_key(i), _issue_key_sort(i), i))
        keyed.sort(key=lambda t: (t[0], t[1]), reverse=not ascending)
        return [t[2] for t in keyed]  # type: ignore[misc]
    return issues


def try_issue_search_from_snapshot(
    pairs: list[tuple[str, str]],
    *,
    now: float | None = None,
) -> dict[str, Any] | None:
    """
    스냅샷으로 issues/search 응답을 만들 수 있으면 dict, 아니면 None.

    None 인 경우: Sonar 프록시로 폴백.
    """
    if not settings.issues_search_from_snapshot:
        return None
    tnow = time.time() if now is None else float(now)
    d = _pairs_last_wins(pairs)
    if d.get("source", "").strip().lower() == "live":
        return None

    ck_raw = d.get("componentKeys", "").strip()
    if not ck_raw:
        return None
    parts = [x.strip() for x in ck_raw.split(",") if x.strip()]
    if len(parts) != 1:
        return None

    row = project_row_by_component_key(parts[0])
    if row is None:
        return None
    pid = str(row.get("id") or "").strip()
    if not pid:
        return None

    ttl = settings.metrics_project_cache_ttl_seconds
    floor_full = severity_floor_for_full_metrics(row)
    issues = issue_snapshot_store.load_issues_if_fresh(
        pid, "full", ttl, tnow, expected_severity_floor=floor_full
    )
    if issues is None:
        return None

    sort_field = d.get("s", "").strip() or None
    if sort_field is None or sort_field == "":
        # Sonar 기본 정렬과 1:1 보장 불가 → 프록시
        return None
    sfu = sort_field.strip().upper()
    if sfu not in ("SEVERITY", "CREATION_DATE"):
        return None

    asc_raw = _parse_bool(d.get("asc"))
    asc = asc_raw if asc_raw is not None else False

    filtered = _filter_issues(
        issues,
        severities_param=d.get("severities"),
        statuses_param=d.get("statuses") or d.get("issueStatuses"),
        authors_param=d.get("authors"),
    )

    team_tid = (d.get("teamId") or "").strip()
    if team_tid:
        filtered = [
            issue
            for issue in filtered
            if isinstance(issue, dict) and team_id_for_issue_row(issue, pid) == team_tid
        ]

    sorted_list = _sort_issues(
        filtered,
        sort_field=sfu,
        asc=asc,
    )

    p = max(1, _parse_int(d.get("p"), 1))
    ps = _parse_int(d.get("ps"), 50)
    ps = max(1, min(ps, 500))

    total = len(sorted_list)
    start = (p - 1) * ps
    page_items = sorted_list[start : start + ps]

    return {
        "total": total,
        "paging": {
            "pageIndex": p,
            "pageSize": ps,
            "total": total,
        },
        "issues": page_items,
    }


def strip_internal_query_params(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Sonar 업스트림에 넘기지 않을 내부 전용 파라미터 제거."""
    return [(k, v) for k, v in pairs if k.lower() not in ("source", "teamid")]
