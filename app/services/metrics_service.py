"""
SonarQube 이슈 전량 수집 후 프로젝트·모듈·Severity 집계 (main-dashboard-platform.md).
"""
from __future__ import annotations

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

_CACHE: dict[str, Any] | None = None
_CACHE_TS: float = 0.0
CACHE_TTL = 90.0


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


async def compute_dashboard_metrics() -> dict[str, Any]:
    global _CACHE, _CACHE_TS
    now = time.time()
    if _CACHE is not None and (now - _CACHE_TS) < CACHE_TTL:
        return _CACHE

    projects_cfg = projects_with_keys()
    by_project: list[dict[str, Any]] = []
    global_severity = _empty_severity_row()
    global_modules: dict[str, dict[str, int]] = {}
    global_chart_stack: dict[str, dict[str, int]] = {}

    errors: list[dict[str, str]] = []

    for row in projects_cfg:
        pid = str(row.get("id") or "")
        label = str(row.get("label") or pid)
        ck = str(row.get("componentKey") or "")
        try:
            issues = await fetch_all_issues(ck)
        except Exception as e:
            errors.append({"projectId": pid, "message": str(e)})
            continue

        st, mods, cstack = _aggregate_issues(issues, pid)
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

        total = sum(st.values())
        by_project.append(
            {
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
        )

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
