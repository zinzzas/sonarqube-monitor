"""
SonarQube 이슈 전량 수집 후 프로젝트·모듈·Severity 집계 (main-dashboard-platform.md).

- 프로젝트별 Sonar 호출은 asyncio.gather 로 병렬화(세마포어로 동시성 상한).
- 프로젝트 단위 캐시 + 조합된 대시보드 응답 캐시(TTL 분리).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from app.config.load_projects import projects_with_keys
from app.core.config import settings
from app.core.module_extract import (
    chart_stack_bucket,
    extract_path_keys_for_rollup,
    module_strategy_for_project,
    profile_id_for_project,
)
from app.core.severity import STANDARD_SEVERITIES, normalize_from_sonar
from app.services.sonarqube_client import sonar_client

# 조합된 `/api/metrics/dashboard` 응답
_CACHE: dict[str, Any] | None = None
_CACHE_TS: float = 0.0

# project_id -> (캐시 시각, byProject 행 dict)
_PROJECT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

_SONAR_SEM: asyncio.Semaphore | None = None


def _sonar_semaphore() -> asyncio.Semaphore:
    global _SONAR_SEM
    if _SONAR_SEM is None:
        n = max(1, int(settings.metrics_sonar_max_concurrent))
        _SONAR_SEM = asyncio.Semaphore(n)
    return _SONAR_SEM


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
        if b not in chart_stack:
            chart_stack[b] = _empty_severity_row()
        chart_stack[b][sev] = chart_stack[b].get(sev, 0) + 1
    return severity_total, modules, chart_stack


def _high_risk(severity_total: dict[str, int]) -> int:
    return severity_total.get("BLOCKER", 0) + severity_total.get("HIGH", 0)


def _search_params(component_key: str, page: int) -> dict[str, str]:
    params: dict[str, str] = {
        "componentKeys": component_key,
        "ps": "500",
        "p": str(page),
        "statuses": "OPEN",
    }
    if settings.sonar_mirror_issue_statuses:
        params["issueStatuses"] = "OPEN"
    return params


async def fetch_all_issues(component_key: str) -> list[dict[str, Any]]:
    all_issues: list[dict[str, Any]] = []
    p = 1
    while True:
        data = await sonar_client.issues_search(_search_params(component_key, p))
        issues = data.get("issues") or []
        all_issues.extend(issues)
        if len(issues) < 500:
            break
        p += 1
    return all_issues


def _build_by_project_row(
    issues: list[dict[str, Any]],
    row: dict[str, Any],
) -> dict[str, Any]:
    pid = str(row.get("id") or "")
    label = str(row.get("label") or pid)
    ck = str(row.get("componentKey") or "")
    st, mods, cstack = _aggregate_issues(issues, pid)
    total = sum(st.values())
    return {
        "projectId": pid,
        "label": label,
        "componentKey": ck,
        "totalIssues": total,
        "severityTotal": st,
        "highRisk": _high_risk(st),
        "modules": mods,
        "chartStackModules": cstack,
        "moduleProfileId": profile_id_for_project(pid),
        "moduleStrategy": module_strategy_for_project(pid),
    }


def _merge_project_row_into_globals(
    row: dict[str, Any],
    global_severity: dict[str, int],
    global_modules: dict[str, dict[str, int]],
    global_chart_stack: dict[str, dict[str, int]],
) -> None:
    st = row["severityTotal"]
    mods = row["modules"]
    cstack = row["chartStackModules"]
    for s, v in st.items():
        global_severity[s] = global_severity.get(s, 0) + v
    for mod, counts in mods.items():
        if mod not in global_modules:
            global_modules[mod] = _empty_severity_row()
        for s, v in counts.items():
            global_modules[mod][s] = global_modules[mod].get(s, 0) + v
    for b, counts in cstack.items():
        if b not in global_chart_stack:
            global_chart_stack[b] = _empty_severity_row()
        for s, v in counts.items():
            global_chart_stack[b][s] = global_chart_stack[b].get(s, 0) + v


def _prune_project_cache(valid_ids: set[str]) -> None:
    for k in list(_PROJECT_CACHE.keys()):
        if k not in valid_ids:
            del _PROJECT_CACHE[k]


async def _fetch_one_project(
    row: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, str | None]:
    """(project_id, by_project 행 또는 None, 오류 메시지 또는 None)"""
    pid = str(row.get("id") or "")
    ck = str(row.get("componentKey") or "")
    try:
        async with _sonar_semaphore():
            issues = await fetch_all_issues(ck)
    except Exception as e:
        return pid, None, str(e)
    row_data = _build_by_project_row(issues, row)
    _PROJECT_CACHE[pid] = (time.time(), row_data)
    return pid, row_data, None


async def compute_dashboard_metrics() -> dict[str, Any]:
    global _CACHE, _CACHE_TS
    now = time.time()
    dash_ttl = settings.metrics_dashboard_cache_ttl_seconds
    proj_ttl = settings.metrics_project_cache_ttl_seconds

    if _CACHE is not None and (now - _CACHE_TS) < dash_ttl:
        return _CACHE

    projects_cfg = projects_with_keys()
    valid_ids = {str(r.get("id") or "") for r in projects_cfg}
    _prune_project_cache(valid_ids)

    cached_by_pid: dict[str, dict[str, Any]] = {}
    to_fetch: list[dict[str, Any]] = []
    for row in projects_cfg:
        pid = str(row.get("id") or "")
        entry = _PROJECT_CACHE.get(pid)
        if entry is not None and (now - entry[0]) < proj_ttl:
            cached_by_pid[pid] = entry[1]
        else:
            to_fetch.append(row)

    errors: list[dict[str, str]] = []
    fetched_map: dict[str, dict[str, Any]] = {}

    if to_fetch:
        results = await asyncio.gather(
            *[_fetch_one_project(r) for r in to_fetch],
            return_exceptions=True,
        )
        for res in results:
            if isinstance(res, BaseException):
                errors.append({"projectId": "_gather", "message": repr(res)})
                continue
            pid, row_data, err = res
            if err is not None:
                errors.append({"projectId": pid, "message": err})
                continue
            if row_data is not None:
                fetched_map[pid] = row_data

    by_project: list[dict[str, Any]] = []
    global_severity = _empty_severity_row()
    global_modules: dict[str, dict[str, int]] = {}
    global_chart_stack: dict[str, dict[str, int]] = {}

    for row in projects_cfg:
        pid = str(row.get("id") or "")
        rdata = cached_by_pid.get(pid) or fetched_map.get(pid)
        if rdata is None:
            continue
        by_project.append(rdata)
        _merge_project_row_into_globals(rdata, global_severity, global_modules, global_chart_stack)

    total_issues = sum(global_severity.values())

    out: dict[str, Any] = {
        "summary": {
            "totalIssues": total_issues,
            "severityTotal": global_severity,
            "highRisk": _high_risk(global_severity),
        },
        "byProject": by_project,
        "globalModules": global_modules,
        "globalChartStackModules": global_chart_stack,
        "errors": errors,
    }

    _CACHE = out
    _CACHE_TS = now
    return out
