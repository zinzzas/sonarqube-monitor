"""
SonarQube 이슈 전량 수집 후 프로젝트·모듈·Severity 집계.

문서: docs/03_design/system-architecture.md, docs/02_analysis/functional-spec.md

- SonarQube 호출은 동시에 여러 건을 날리지 않고, 프로젝트(및 페이징) 단위로 순차(await) 처리.
- 대시보드는 요청한 projectId 한 건만 집계해 응답(고객사 서버 부하 완화).
- 프로젝트 단위 캐시 + 대시보드 응답 캐시(TTL 분리).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.config.load_projects import project_labels_map, projects_with_keys
from app.core.config import settings
from app.core.module_extract import (
    chart_stack_bucket,
    extract_path_keys_for_rollup,
    module_strategy_for_project,
    profile_id_for_project,
)
from app.core.severity import STANDARD_SEVERITIES, normalize_from_sonar
from app.core.team_high_risk import (
    aggregate_high_risk_by_team,
    team_display_order,
    team_labels_from_config,
)
from app.services.sonarqube_issues_fetch import fetch_all_issues

# 조합된 `/api/metrics/dashboard` 응답 (단일 projectId 기준)
_CACHE: dict[str, Any] | None = None
_CACHE_TS: float = 0.0
_DASH_CACHE_PROJECT: str | None = None

# project_id -> (캐시 시각, byProject 행 dict, Sonar 이슈 원본 목록)
_PROJECT_CACHE: dict[str, tuple[float, dict[str, Any], list[dict[str, Any]]]] = {}


def invalidate_dashboard_cache() -> None:
    """
    `module_segment_labels.json` 의 teamMapping 저장 직후 호출.

    - 조합된 대시보드 응답 캐시(`_CACHE`) 제거 → summary의 팀 라벨·순서가 파일 기준으로 다시 채워짐.
    - 프로젝트별 이슈·집계 캐시(`_PROJECT_CACHE`) 제거 → `highRiskByTeam` 이 새 매칭 규칙으로 다시 계산됨
      (캐시된 행만 갱신하면 규칙 변경 시 버킷 건수가 어긋날 수 있음).
    """
    global _CACHE, _CACHE_TS, _DASH_CACHE_PROJECT
    _CACHE = None
    _CACHE_TS = 0.0
    _DASH_CACHE_PROJECT = None
    _PROJECT_CACHE.clear()


def _severity_key(raw: str | None) -> str:
    if not raw:
        return "INFO"
    n = normalize_from_sonar(raw)
    if n in STANDARD_SEVERITIES:
        return n
    return "INFO"


def _empty_severity_row() -> dict[str, int]:
    return {s: 0 for s in STANDARD_SEVERITIES}


def _aggregate_issues(
    issues: list[dict[str, Any]],
    project_id: str,
) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    severity_total = _empty_severity_row()
    modules: dict[str, dict[str, int]] = {}
    chart_stack: dict[str, dict[str, int]] = {}
    for issue in issues:
        comp = issue.get("component") or ""
        sev = _severity_key(issue.get("severity"))
        severity_total[sev] = severity_total.get(sev, 0) + 1
        for mod in extract_path_keys_for_rollup(comp, project_id):
            if mod not in modules:
                modules[mod] = _empty_severity_row()
            modules[mod][sev] = modules[mod].get(sev, 0) + 1
        b = chart_stack_bucket(comp, project_id)
        if b is not None and b != "":
            if b not in chart_stack:
                chart_stack[b] = _empty_severity_row()
            chart_stack[b][sev] = chart_stack[b].get(sev, 0) + 1
    return severity_total, modules, chart_stack


def _high_risk(severity_total: dict[str, int]) -> int:
    return severity_total.get("BLOCKER", 0) + severity_total.get("HIGH", 0)


def _issue_export_dict(issue: dict[str, Any], project_id: str, label: str) -> dict[str, Any]:
    """엑셀/CSV용 펼친 행 — 집계와 동일 OPEN 이슈."""
    comp = issue.get("component") or ""
    msg = issue.get("message") or ""
    if isinstance(msg, str):
        msg = msg.replace("\r\n", " ").replace("\n", " ").strip()
    line = issue.get("line")
    line_out: int | None = line if isinstance(line, int) else None
    return {
        "projectId": project_id,
        "projectLabel": label,
        "severity": _severity_key(issue.get("severity")),
        "moduleBucket": chart_stack_bucket(comp, project_id) or "",
        "component": comp,
        "line": line_out,
        "message": msg,
        "rule": issue.get("rule") or "",
        "status": issue.get("status") or "",
        "key": issue.get("key") or "",
    }


def _sort_key_flat(r: dict[str, Any]) -> tuple:
    ln = r.get("line")
    ln_key = ln if isinstance(ln, int) else -1
    return (r["projectLabel"], r["moduleBucket"], r["severity"], r["component"], ln_key)


async def export_flat_issues_json() -> dict[str, Any]:
    """
    프로젝트별 Module×Severity 집계와 동일 소스(OPEN 전량)를 이슈 단위로 펼친 목록.
    프로젝트마다 Sonar 호출을 순차 처리(병렬 호출 없음). 캐시가 있으면 재사용.
    """
    labels_map = project_labels_map()
    projects_cfg = projects_with_keys()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for row in projects_cfg:
        pid = str(row.get("id") or "")
        res_pid, row_data, err = await _fetch_one_project(row, labels_map)
        if err is not None:
            errors.append({"projectId": res_pid, "message": err})
            continue
        if row_data is None:
            continue
        entry = _PROJECT_CACHE.get(pid)
        if entry is None or len(entry) < 3:
            errors.append({"projectId": pid, "message": "no_issue_payload"})
            continue
        issues = entry[2]
        label = labels_map.get(pid) or str(row.get("label") or pid)
        for issue in issues:
            rows.append(_issue_export_dict(issue, pid, label))
    rows.sort(key=_sort_key_flat)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "issues": rows,
        "errors": errors,
    }


def _with_canonical_label(
    row: dict[str, Any],
    labels_map: dict[str, str],
) -> dict[str, Any]:
    """projectId 기준으로 `component_projects.json` 라벨을 강제(캐시에 남은 옛 label 제거)."""
    pid = str(row.get("projectId") or "")
    if pid and pid in labels_map:
        return {**row, "label": labels_map[pid]}
    return row


def _build_by_project_row(
    issues: list[dict[str, Any]],
    row: dict[str, Any],
    labels_map: dict[str, str],
) -> dict[str, Any]:
    pid = str(row.get("id") or "")
    label = labels_map.get(pid) or str(row.get("label") or pid)
    ck = str(row.get("componentKey") or "")
    st, mods, cstack = _aggregate_issues(issues, pid)
    total = sum(st.values())
    hr_by_team = aggregate_high_risk_by_team(
        issues,
        pid,
        severity_key_fn=_severity_key,
        is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
    )
    return {
        "projectId": pid,
        "label": label,
        "componentKey": ck,
        "totalIssues": total,
        "severityTotal": st,
        "highRisk": _high_risk(st),
        "highRiskByTeam": hr_by_team,
        "modules": mods,
        "chartStackModules": cstack,
        "moduleProfileId": profile_id_for_project(pid),
        "moduleStrategy": module_strategy_for_project(pid),
    }


def _prune_project_cache(valid_ids: set[str]) -> None:
    for k in list(_PROJECT_CACHE.keys()):
        if k not in valid_ids:
            del _PROJECT_CACHE[k]


async def _fetch_one_project(
    row: dict[str, Any],
    labels_map: dict[str, str],
) -> tuple[str, dict[str, Any] | None, str | None]:
    """(project_id, by_project 행 또는 None, 오류 메시지 또는 None). Sonar 호출은 순차 1건씩."""
    pid = str(row.get("id") or "")
    ck = str(row.get("componentKey") or "").strip()
    now = time.time()
    proj_ttl = settings.metrics_project_cache_ttl_seconds
    entry = _PROJECT_CACHE.get(pid)
    if entry is not None and len(entry) >= 3 and (now - entry[0]) < proj_ttl:
        return pid, entry[1], None

    if not ck:
        row_data = _build_by_project_row([], row, labels_map)
        _PROJECT_CACHE[pid] = (time.time(), row_data, [])
        return pid, row_data, None

    try:
        issues = await fetch_all_issues(ck)
    except Exception as e:
        return pid, None, str(e)
    row_data = _build_by_project_row(issues, row, labels_map)
    _PROJECT_CACHE[pid] = (time.time(), row_data, issues)
    return pid, row_data, None


def _empty_dashboard(project_id: str = "") -> dict[str, Any]:
    es = _empty_severity_row()
    tm_labels = team_labels_from_config()
    tm_order = team_display_order()
    empty_teams = {tid: 0 for tid in tm_order} if tm_order else {"shared": 0}
    return {
        "summary": {
            "totalIssues": 0,
            "severityTotal": es,
            "highRisk": 0,
            "highRiskByTeam": empty_teams,
            "highRiskTeamLabels": tm_labels,
            "highRiskTeamOrder": tm_order,
        },
        "byProject": [],
        "globalModules": {},
        "globalChartStackModules": {},
        "errors": [{"projectId": project_id or "_", "message": "no_data"}],
        "projectId": project_id or None,
    }


async def compute_dashboard_metrics(project_id: str | None = None) -> dict[str, Any]:
    """단일 projectId 집계만 수행. Sonar는 해당 프로젝트(및 issues 페이징)만 순차 호출."""
    global _CACHE, _CACHE_TS, _DASH_CACHE_PROJECT
    now = time.time()
    dash_ttl = settings.metrics_dashboard_cache_ttl_seconds

    labels_map = project_labels_map()
    projects_cfg = projects_with_keys()
    valid_ids = {str(r.get("id") or "") for r in projects_cfg}
    _prune_project_cache(valid_ids)

    if not projects_cfg:
        out = _empty_dashboard()
        _CACHE = out
        _CACHE_TS = now
        _DASH_CACHE_PROJECT = None
        return out

    pid_req = str(project_id or "").strip() or str(projects_cfg[0].get("id") or "")
    row_cfg = next((r for r in projects_cfg if str(r.get("id") or "") == pid_req), None)
    if row_cfg is None:
        out = _empty_dashboard(pid_req)
        _CACHE = out
        _CACHE_TS = now
        _DASH_CACHE_PROJECT = pid_req
        return out

    if (
        _CACHE is not None
        and _DASH_CACHE_PROJECT == pid_req
        and (now - _CACHE_TS) < dash_ttl
    ):
        return _CACHE

    errors: list[dict[str, str]] = []
    res_pid, row_data, err = await _fetch_one_project(row_cfg, labels_map)
    if err is not None:
        errors.append({"projectId": res_pid, "message": err})
    if row_data is None:
        row_data = _build_by_project_row([], row_cfg, labels_map)

    row_data = _with_canonical_label(row_data, labels_map)
    st = row_data["severityTotal"]
    total = sum(st.values())
    hr_team = dict(row_data.get("highRiskByTeam") or {})
    tm_labels = team_labels_from_config()
    tm_order = team_display_order()

    out: dict[str, Any] = {
        "summary": {
            "totalIssues": total,
            "severityTotal": st,
            "highRisk": _high_risk(st),
            "highRiskByTeam": hr_team,
            "highRiskTeamLabels": tm_labels,
            "highRiskTeamOrder": tm_order,
        },
        "byProject": [row_data],
        "globalModules": dict(row_data.get("modules") or {}),
        "globalChartStackModules": dict(row_data.get("chartStackModules") or {}),
        "errors": errors,
        "projectId": pid_req,
    }

    _CACHE = out
    _CACHE_TS = now
    _DASH_CACHE_PROJECT = pid_req
    return out
