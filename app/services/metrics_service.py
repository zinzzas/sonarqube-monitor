"""
SonarQube 이슈 전량 수집 후 프로젝트·모듈·Severity 집계.

문서: docs/03_design/system-architecture.md, docs/02_analysis/functional-spec.md

- SonarQube 호출은 동시에 여러 건을 날리지 않고, 프로젝트(및 페이징) 단위로 순차(await) 처리.
- 대시보드는 기본적으로 요청한 projectId 한 건만 집계(고객사 서버 부하 완화).
- `projectId=all` 이면 전 프로젝트를 순차 집계하되, Sonar는 OPEN·BLOCKER/HIGH/MEDIUM(B·H·M)만 수집.
- 프로젝트 단위 메모리 캐시 + 디스크 스냅샷(`issue_snapshot_store`) + 대시보드 응답 캐시(TTL·`severityFloor` 정합).
- 모듈·차트·CSV 집계는 `issue_component_key`(웹과 동일)로 경로 문자열을 취한다.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.config.load_projects import (
    load_component_projects,
    project_labels_map,
    projects_with_keys,
    severity_floor_for_aggregate_scope,
    severity_floor_for_full_metrics,
)
from app.core.config import settings
from app.core.module_extract import (
    chart_stack_bucket,
    extract_path_keys_for_rollup,
    module_strategy_for_project,
    profile_id_for_project,
)
from app.core.severity import STANDARD_SEVERITIES, severity_bucket_for_issue
from app.core.team_high_risk import (
    aggregate_high_risk_by_team,
    issue_component_key,
    team_display_order,
    team_labels_from_config,
)
from app.services import issue_snapshot_coordinator, issue_snapshot_store
from app.services.sonarqube_issues_fetch import (
    fetch_all_issues,
    fetch_open_issues_for_floor,
)

# 조합된 `/api/metrics/dashboard` 응답 (단일 projectId 또는 all)
_CACHE: dict[str, Any] | None = None
_CACHE_TS: float = 0.0
_DASH_CACHE_PROJECT: str | None = None

# project_id -> (캐시 시각, byProject 행 dict, Sonar 이슈 원본 목록)
_PROJECT_CACHE: dict[str, tuple[float, dict[str, Any], list[dict[str, Any]]]] = {}
# 동일 — OPEN 이슈를 B·H·M(Sonar BLOCKER/CRITICAL/MAJOR)만 수집한 집계용
_PROJECT_CACHE_BHM: dict[str, tuple[float, dict[str, Any], list[dict[str, Any]]]] = {}

# 대시보드 ALL 예약어 — component_projects.json 의 id 와 충돌 시 `projectId` 를 바꾸거나 id 를 변경할 것
_ALL_SCOPE_TOKEN = "all"


def _normalize_dashboard_project_id(project_id: str | None) -> str:
    """쿼리 projectId — ZWSP 등으로 'all' 분기가 깨지는 것 방지."""
    if project_id is None:
        return ""
    s = str(project_id).strip()
    for ch in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u200e", "\u200f"):
        s = s.replace(ch, "")
    return s.strip()


def _component_projects_rows() -> list[dict[str, Any]]:
    """`component_projects.json` 전체 — id 가 있는 행만 (componentKey 없어도 포함)."""
    rows = load_component_projects()
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        pid = str(r.get("id") or "").strip()
        if not pid:
            continue
        out.append(r)
    return out


def invalidate_dashboard_cache() -> None:
    """
    `module_segment_labels.json` 의 teamMapping 저장 직후 호출.

    - 조합된 대시보드 응답 캐시(`_CACHE`) 제거 → summary의 팀 라벨·순서가 파일 기준으로 다시 채워짐.
    - 프로젝트별 이슈·집계 캐시(`_PROJECT_CACHE`, `_PROJECT_CACHE_BHM`) 제거 → `highRiskByTeam` 이 새 매칭 규칙으로 다시 계산됨
      (캐시된 행만 갱신하면 규칙 변경 시 버킷 건수가 어긋날 수 있음).
    """
    global _CACHE, _CACHE_TS, _DASH_CACHE_PROJECT
    _CACHE = None
    _CACHE_TS = 0.0
    _DASH_CACHE_PROJECT = None
    _PROJECT_CACHE.clear()
    _PROJECT_CACHE_BHM.clear()
    issue_snapshot_store.clear_all_snapshots()


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
        comp = issue_component_key(issue)
        sev = severity_bucket_for_issue(issue)
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
    comp = issue_component_key(issue)
    msg = issue.get("message") or ""
    if isinstance(msg, str):
        msg = msg.replace("\r\n", " ").replace("\n", " ").strip()
    line = issue.get("line")
    line_out: int | None = line if isinstance(line, int) else None
    return {
        "projectId": project_id,
        "projectLabel": label,
        "severity": severity_bucket_for_issue(issue),
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
        severity_key_fn=severity_bucket_for_issue,
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
    for k in list(_PROJECT_CACHE_BHM.keys()):
        if k not in valid_ids:
            del _PROJECT_CACHE_BHM[k]
    issue_snapshot_store.prune_orphan_dirs(valid_ids)


async def _fetch_one_project(
    row: dict[str, Any],
    labels_map: dict[str, str],
) -> tuple[str, dict[str, Any] | None, str | None]:
    """(project_id, by_project 행 또는 None, 오류 메시지 또는 None). Sonar 호출은 순차 1건씩."""
    pid = str(row.get("id") or "")
    ck = str(row.get("componentKey") or "").strip()
    now = time.time()
    proj_ttl = settings.metrics_project_cache_ttl_seconds
    floor_full = severity_floor_for_full_metrics(row)
    entry = _PROJECT_CACHE.get(pid)
    if entry is not None and len(entry) >= 3 and (now - entry[0]) < proj_ttl:
        return pid, entry[1], None

    if not ck:
        row_data = _build_by_project_row([], row, labels_map)
        _PROJECT_CACHE[pid] = (time.time(), row_data, [])
        return pid, row_data, None

    snap = issue_snapshot_store.load_issues_if_fresh(
        pid, "full", proj_ttl, time.time(), expected_severity_floor=floor_full
    )
    if snap is not None:
        row_data = _build_by_project_row(snap, row, labels_map)
        _PROJECT_CACHE[pid] = (time.time(), row_data, snap)
        return pid, row_data, None

    lock = issue_snapshot_coordinator.lock_for(pid, "full")
    async with lock:
        now2 = time.time()
        entry2 = _PROJECT_CACHE.get(pid)
        if entry2 is not None and len(entry2) >= 3 and (now2 - entry2[0]) < proj_ttl:
            return pid, entry2[1], None
        snap2 = issue_snapshot_store.load_issues_if_fresh(
            pid, "full", proj_ttl, time.time(), expected_severity_floor=floor_full
        )
        if snap2 is not None:
            row_data = _build_by_project_row(snap2, row, labels_map)
            _PROJECT_CACHE[pid] = (time.time(), row_data, snap2)
            return pid, row_data, None
        try:
            issues = await fetch_all_issues(ck, floor_full)
        except Exception as e:
            return pid, None, str(e)
        issue_snapshot_store.save_issues(pid, "full", issues, ck, severity_floor=floor_full)
        row_data = _build_by_project_row(issues, row, labels_map)
        _PROJECT_CACHE[pid] = (time.time(), row_data, issues)
        return pid, row_data, None


async def _fetch_one_project_bhm(
    row: dict[str, Any],
    labels_map: dict[str, str],
) -> tuple[str, dict[str, Any] | None, str | None]:
    """OPEN 이슈 중 B·H·M만. 캐시는 전체 집계(`_PROJECT_CACHE`)와 분리."""
    pid = str(row.get("id") or "")
    ck = str(row.get("componentKey") or "").strip()
    now = time.time()
    proj_ttl = settings.metrics_project_cache_ttl_seconds
    floor_bhm = severity_floor_for_aggregate_scope(row)
    entry = _PROJECT_CACHE_BHM.get(pid)
    if entry is not None and len(entry) >= 3 and (now - entry[0]) < proj_ttl:
        return pid, entry[1], None

    if not ck:
        row_data = _build_by_project_row([], row, labels_map)
        _PROJECT_CACHE_BHM[pid] = (time.time(), row_data, [])
        return pid, row_data, None

    snap = issue_snapshot_store.load_issues_if_fresh(
        pid, "bhm", proj_ttl, time.time(), expected_severity_floor=floor_bhm
    )
    if snap is not None:
        row_data = _build_by_project_row(snap, row, labels_map)
        _PROJECT_CACHE_BHM[pid] = (time.time(), row_data, snap)
        return pid, row_data, None

    lock = issue_snapshot_coordinator.lock_for(pid, "bhm")
    async with lock:
        now2 = time.time()
        entry2 = _PROJECT_CACHE_BHM.get(pid)
        if entry2 is not None and len(entry2) >= 3 and (now2 - entry2[0]) < proj_ttl:
            return pid, entry2[1], None
        snap2 = issue_snapshot_store.load_issues_if_fresh(
            pid, "bhm", proj_ttl, time.time(), expected_severity_floor=floor_bhm
        )
        if snap2 is not None:
            row_data = _build_by_project_row(snap2, row, labels_map)
            _PROJECT_CACHE_BHM[pid] = (time.time(), row_data, snap2)
            return pid, row_data, None
        try:
            issues = await fetch_open_issues_for_floor(ck, floor_bhm)
        except Exception as e:
            return pid, None, str(e)
        issue_snapshot_store.save_issues(pid, "bhm", issues, ck, severity_floor=floor_bhm)
        row_data = _build_by_project_row(issues, row, labels_map)
        _PROJECT_CACHE_BHM[pid] = (time.time(), row_data, issues)
        return pid, row_data, None


def _merge_severity_totals_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = _empty_severity_row()
    for r in rows:
        st = r.get("severityTotal") or {}
        for s in STANDARD_SEVERITIES:
            out[s] = out.get(s, 0) + int(st.get(s, 0))
    return out


def _merge_high_risk_by_team_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        for tid, n in (r.get("highRiskByTeam") or {}).items():
            out[tid] = out.get(tid, 0) + int(n)
    return out


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
        "aggregateMode": "project_full",
    }


async def _compute_dashboard_all_bhm(
    labels_map: dict[str, str],
    project_rows: list[dict[str, Any]],
    dash_ttl: float,
    now: float,
) -> dict[str, Any]:
    """전 프로젝트·OPEN·B·H·M만 순차 수집 후 요약 병합. componentKey 없으면 Sonar 미호출·0건."""
    global _CACHE, _CACHE_TS, _DASH_CACHE_PROJECT

    if (
        _CACHE is not None
        and _DASH_CACHE_PROJECT == _ALL_SCOPE_TOKEN
        and (now - _CACHE_TS) < dash_ttl
    ):
        return _CACHE

    errors: list[dict[str, str]] = []
    rows_out: list[dict[str, Any]] = []
    for row_cfg in project_rows:
        res_pid, row_data, err = await _fetch_one_project_bhm(row_cfg, labels_map)
        if err is not None:
            errors.append({"projectId": res_pid, "message": err})
        if row_data is None:
            row_data = _build_by_project_row([], row_cfg, labels_map)
        else:
            row_data = _with_canonical_label(row_data, labels_map)
        rows_out.append(row_data)

    st_merged = _merge_severity_totals_from_rows(rows_out)
    total = sum(st_merged.values())
    hr_team = _merge_high_risk_by_team_rows(rows_out)
    tm_labels = team_labels_from_config()
    tm_order = team_display_order()
    for tid in tm_order:
        hr_team.setdefault(tid, 0)

    out: dict[str, Any] = {
        "summary": {
            "totalIssues": total,
            "severityTotal": st_merged,
            "highRisk": _high_risk(st_merged),
            "highRiskByTeam": hr_team,
            "highRiskTeamLabels": tm_labels,
            "highRiskTeamOrder": tm_order,
        },
        "byProject": rows_out,
        "globalModules": {},
        "globalChartStackModules": {},
        "errors": errors,
        "projectId": _ALL_SCOPE_TOKEN,
        "aggregateMode": "all_bhm",
    }

    _CACHE = out
    _CACHE_TS = now
    _DASH_CACHE_PROJECT = _ALL_SCOPE_TOKEN
    return out


async def compute_dashboard_metrics(project_id: str | None = None) -> dict[str, Any]:
    """
    대시보드 집계.

    - `projectId=all`: `component_projects.json` 전체 행 기준 병합(키 없으면 0건). OPEN·B·H·M만 Sonar 호출.
    - 그 외: 단일 프로젝트·OPEN 전 심각도(`fetch_all_issues`) — componentKey 있는 행만 `projects_with_keys()`.
    """
    global _CACHE, _CACHE_TS, _DASH_CACHE_PROJECT
    now = time.time()
    dash_ttl = settings.metrics_dashboard_cache_ttl_seconds

    labels_map = project_labels_map()
    raw = _normalize_dashboard_project_id(project_id)
    all_cfg_rows = _component_projects_rows()
    valid_ids = {str(r.get("id") or "").strip() for r in all_cfg_rows}
    _prune_project_cache(valid_ids)

    # ALL 은 projects_with_keys() 비어 있어도 진행 (키 없는 프로젝트는 0건). JSON 자체가 비었을 때만 빈 대시보드.
    if raw.lower() == _ALL_SCOPE_TOKEN:
        if not all_cfg_rows:
            out = _empty_dashboard()
            _CACHE = out
            _CACHE_TS = now
            _DASH_CACHE_PROJECT = None
            return out
        return await _compute_dashboard_all_bhm(labels_map, all_cfg_rows, dash_ttl, now)

    projects_cfg = projects_with_keys()
    if not projects_cfg:
        out = _empty_dashboard()
        _CACHE = out
        _CACHE_TS = now
        _DASH_CACHE_PROJECT = None
        return out

    pid_req = raw or str(projects_cfg[0].get("id") or "")
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
        "aggregateMode": "project_full",
    }

    _CACHE = out
    _CACHE_TS = now
    _DASH_CACHE_PROJECT = pid_req
    return out
