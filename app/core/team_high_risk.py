"""
HIGH RISK(BLOCKER+HIGH) 이슈를 `module_segment_labels.json` 의 `teamMapping` 으로 팀 버킷에 나눈다.

**대시보드와의 연결**
- `metrics_service._build_by_project_row` 가 Sonar에서 모은 OPEN 이슈 목록에 대해
  `aggregate_high_risk_by_team` 을 호출하고, 반환값이 API 응답 `highRiskByTeam` 이 된다.
- UI의 “개발1팀 / 개발2팀 / … / ETC(미분류)” 건수는 모두 이 모듈의 규칙으로만 결정된다.

**분류 기준(요약)**
1. 심각도: 표준 버킷이 BLOCKER 또는 HIGH 인 이슈만 집계 대상(`is_high_risk_fn`).
2. 경로: Sonar `component`(또는 `mainComponent.key`) 문자열에서 `module_grouping.json` 의
   해당 `projectId` 프로필(`path_tree` / `split_after`)에 따라 **디렉터리 토큰 목록** `segments` 를 만든다.
3. 팀: `teamMapping.precedence` 를 **위에서부터** 순회하며, `when`(modules + match first/any) 이
   `segments` 와 처음으로 맞는 행의 `teamId` 가 버킷이다. 아무 것도 안 맞으면 `fallback`(예: shared=ETC).

**디버그**
- `Settings.team_match_debug_log` 에 파일 경로를 주면 BLOCKER/HIGH 이슈마다 JSON 한 줄씩 기록한다.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.config.load_module_segment_labels import team_mapping_config
from app.core.config import settings
from app.core.module_extract import (
    extract_module,
    profile_for_project,
    profile_id_for_project,
    split_after_path_segments,
)
from app.core.module_path_tree import path_tree_segments, sonar_relative_path, strip_only_path_segments

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEAM_MATCH_DEBUG_LOCK = threading.Lock()

# 팀 매칭 fallback 시 경로 깊이(anchor 미매칭·split_after unknown 등) — 프로필 maxDepth(예: 2)보다 넓게 토큰 검사
_TEAM_MATCH_MAX_DEPTH = 32

# `profiles.<id>.teamMatch` 에서 팀 전용으로 덮어쓸 수 있는 키 (module_grouping.json)
_TEAM_MATCH_PROFILE_KEYS = frozenset(
    {"stripPrefixes", "anchorAfter", "chartStackAnchorAfter", "maxDepth"}
)


def _append_team_match_debug_line(record: dict[str, Any]) -> None:
    """`settings.team_match_debug_log` 가 설정된 경우에만 JSON Lines append (프로세스 내 단일 락)."""
    raw = (settings.team_match_debug_log or "").strip()
    if not raw:
        return
    path = Path(raw)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        with _TEAM_MATCH_DEBUG_LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
    except OSError:
        return


def _norm_path_substring(s: str) -> str:
    return str(s or "").replace("\\", "/").strip()


def _team_match_block(profile: dict[str, Any]) -> dict[str, Any] | None:
    tm = profile.get("teamMatch")
    return tm if isinstance(tm, dict) and tm else None


def _path_passes_team_match_gate(full_path: str, team_match: dict[str, Any]) -> bool:
    """pathMustContain 이 비어 있지 않으면 Sonar 상대 경로에 부분 문자열(대소문자 무시)이 있어야 팀 토큰 추출."""
    needle = str(team_match.get("pathMustContain") or "").strip()
    if not needle:
        return True
    h = _norm_path_substring(full_path).lower()
    return needle.lower() in h


def _profile_effective_for_team_path_tree(profile: dict[str, Any]) -> dict[str, Any]:
    """teamMatch 가 strip/anchor/maxDepth 를 주면 팀 매칭 path_tree 전처리에만 반영."""
    tm = _team_match_block(profile)
    if not tm:
        return profile
    out = dict(profile)
    for k in _TEAM_MATCH_PROFILE_KEYS:
        if k in tm:
            out[k] = tm[k]
    return out


def _path_tree_team_segments(component: str | None, project_id: str | None) -> list[str]:
    profile = profile_for_project(project_id)
    tm = _team_match_block(profile)
    if tm:
        path_full = sonar_relative_path(component)
        if not path_full or not _path_passes_team_match_gate(path_full, tm):
            return []
    eff = _profile_effective_for_team_path_tree(profile)
    segs = path_tree_segments(component, eff)
    if segs:
        return segs
    anchor = str(eff.get("anchorAfter") or "").strip()
    if anchor:
        return []
    return strip_only_path_segments(
        component, eff, max_depth_override=_TEAM_MATCH_MAX_DEPTH
    )


def _norm_seg(s: str) -> str:
    return str(s or "").strip().lower()


def _split_after_anchor_missing_in_path(component: str | None, profile: dict[str, Any]) -> bool:
    """split_after 의 `after`(기본 /fims/) 가 component 경로에 없으면 True — strip 폴백 금지 판단용."""
    path = sonar_relative_path(component)
    if not path:
        return False
    after = str(profile.get("after") or "/fims/")
    return path.find(after) < 0


def _path_segments_for_issue(component: str | None, project_id: str | None) -> list[str]:
    """
    path_tree / split_after 모두 지원. 모듈 exclude 와 무관하게 경로만 사용.

    **path_tree**
    - `teamMatch` 가 있으면: `pathMustContain` 이 있을 때 Sonar 상대 경로에 없으면 빈 리스트.
      `teamMatch.stripPrefixes` / `anchorAfter` / `maxDepth` 등은 팀 매칭용으로만 프로필을 덮어씀.
    - 그 외: `anchorAfter` 가 비어 있지 않으면 path_tree_segments 만 사용; 앵커 미매칭 시 빈 리스트.
    - `anchorAfter` 가 비어 있으면(vue_src_tree 등): 위가 비면 strip_only 폴백.

    **split_after**
    - `extract_module` 이 알려진 모듈이면 그 1토큰.
    - 그렇지 않으면 `after` 이후 세그먼트 목록.
    - 그것도 비고 경로에 `after` 가 아예 없으면 빈 리스트 — strip_only 폴백 없음.
    """
    profile = profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        return _path_tree_team_segments(component, project_id)
    if strategy == "split_after":
        mod = extract_module(component, project_id, profile=profile)
        if mod and mod != "unknown":
            return [mod]
        after_segs = split_after_path_segments(component, profile)
        if after_segs:
            return after_segs
        if _split_after_anchor_missing_in_path(component, profile):
            return []
        return strip_only_path_segments(
            component, profile, max_depth_override=_TEAM_MATCH_MAX_DEPTH
        )
    mod = extract_module(component, project_id, profile=profile)
    if mod and mod != "unknown":
        return [mod]
    after_segs = split_after_path_segments(component, profile)
    if after_segs:
        return after_segs
    return strip_only_path_segments(
        component, profile, max_depth_override=_TEAM_MATCH_MAX_DEPTH
    )


def path_segments_for_team_match(component: str | None, project_id: str | None) -> list[str]:
    """이슈 component → 팀 매칭에 쓰는 경로 세그먼트(테스트·대시보드 디버그용)."""
    return _path_segments_for_issue(component, project_id)


def issue_component_key(issue: dict[str, Any] | None) -> str:
    """
    웹 `issueComponentKey` 와 동일 — Sonar 이슈에서 component 문자열.
    (일부 응답은 `component` 대신 `mainComponent.key` 만 준다.)
    """
    if not issue or not isinstance(issue, dict):
        return ""
    c = issue.get("component")
    if isinstance(c, str) and c.strip():
        return c.strip()
    if isinstance(c, dict):
        mk = c.get("key")
        if isinstance(mk, str) and mk.strip():
            return mk.strip()
    ck = issue.get("componentKey")
    if isinstance(ck, str) and ck.strip():
        return ck.strip()
    main = issue.get("mainComponent")
    if isinstance(main, str) and main.strip():
        return main.strip()
    if isinstance(main, dict):
        k = main.get("key")
        if isinstance(k, str) and k.strip():
            return k.strip()
    return ""


def team_id_for_issue_row(issue: dict[str, Any] | None, project_id: str) -> str:
    """
    웹 `teamIdForIssue` 와 동일 규칙 — 경로 세그먼트 + teamMapping.
    """
    comp = issue_component_key(issue)
    segs = path_segments_for_team_match(comp, project_id)
    return team_id_for_path_segments(segs, team_mapping_config())


def _when_str_list(when: dict[str, Any], key: str, legacy_key: str) -> list[Any]:
    v = when.get(key)
    if v is None:
        v = when.get(legacy_key)
    return v if isinstance(v, list) else []


def _norm_module_list(raw: list[Any]) -> list[str]:
    return [_norm_seg(x) for x in raw if x]


def _coerce_when_match_kind(when: dict[str, Any]) -> Literal["first", "any"]:
    """
    신형 teamMapping.when 의 match 정규화.
    누락·오타·그 외 값은 any (과거: 잘못된 match 로 전 precedence 미매칭 → 전부 fallback).
    """
    mk = str(when.get("match") or "").strip().lower()
    return "first" if mk == "first" else "any"


def _match_new_style_when(seg_l: list[str], when: dict[str, Any]) -> bool | None:
    """
    { "modules": [...], "match": "first"|"any" } 만 처리.
    신형 키가 없거나 modules 가 비어 있으면 None → 구형 when 키로 폴백.
    """
    if "modules" not in when or not isinstance(when.get("modules"), list):
        return None
    mods = _norm_module_list(when["modules"])
    if not mods:
        return None
    kind = _coerce_when_match_kind(when)
    if kind == "first":
        return seg_l[0] in mods
    return any(s in mods for s in seg_l)


def _match_legacy_when(seg_l: list[str], when: dict[str, Any]) -> bool:
    """구형 firstModule/anyModule·firstSegment/anySegment (둘 다 있으면 OR)."""
    fs = _norm_module_list(_when_str_list(when, "firstModule", "firstSegment"))
    anys = _norm_module_list(_when_str_list(when, "anyModule", "anySegment"))
    if fs and not anys:
        return seg_l[0] in fs
    if anys and not fs:
        return any(s in anys for s in seg_l)
    if fs and anys:
        return seg_l[0] in fs or any(s in anys for s in seg_l)
    return False


def _match_when(segments: list[str], when: dict[str, Any]) -> bool:
    if not when:
        return False
    seg_l = [_norm_seg(s) for s in segments if s]
    if not seg_l:
        return False

    new_style = _match_new_style_when(seg_l, when)
    if new_style is not None:
        return new_style

    return _match_legacy_when(seg_l, when)


def team_id_for_path_segments(segments: list[str], mapping: dict[str, Any] | None = None) -> str:
    """
    precedence 규칙 중 첫 매칭 teamId, 없으면 fallback.teamId.
    mapping 이 비어 있으면 항상 fallback 또는 'shared'.
    """
    cfg = mapping if mapping is not None else team_mapping_config()
    prec = cfg.get("precedence") or []
    if isinstance(prec, list):
        for row in prec:
            if not isinstance(row, dict):
                continue
            tid = str(row.get("teamId") or "").strip()
            w = row.get("when")
            if tid and isinstance(w, dict) and _match_when(segments, w):
                return tid
    fb = cfg.get("fallback")
    if isinstance(fb, dict):
        fid = str(fb.get("teamId") or "").strip()
        if fid:
            return fid
    return "shared"


def aggregate_high_risk_by_team(
    issues: list[dict[str, Any]],
    project_id: str,
    *,
    severity_key_fn: Any,
    is_high_risk_fn: Any,
) -> dict[str, int]:
    """
    대시보드 **High risk(BLOCKER+HIGH) 팀별 건수** (`highRiskByTeam`) 의 유일한 계산 함수.

    **입력**
    - `issues`: 해당 Sonar component(프로젝트)의 OPEN 이슈 목록(집계·스냅샷과 동일 소스).
    - `severity_key_fn(issue)`: 이슈 dict → 표준 심각도 버킷(`BLOCKER`, `HIGH`, …).
      `metrics_service` 는 `severity_bucket_for_issue` 를 넘긴다.
    - `is_high_risk_fn(sev)`: 보통 `lambda s: s in ("BLOCKER", "HIGH")`.

    **동작**
    1. 위 조건을 통과한 이슈만 대상.
    2. `issue_component_key` 로 Sonar 경로 문자열 확보 (`mainComponent.key` 폴백 포함).
    3. `path_segments_for_team_match` → `module_grouping` 프로필에 따라 슬래시 토큰 배열 생성.
    4. `team_id_for_path_segments` → `module_segment_labels.teamMapping` 의 precedence 첫 매칭 팀,
       없으면 fallback(예: shared = UI의 ETC/미분류).

    **디버그 로그** (`settings.team_match_debug_log` 비어 있지 않을 때)
    - 위 HIGH RISK 이슈마다 JSON 한 줄: component, segments, teamId, moduleProfileId 등.
    - 패키지 구조가 다른 프로젝트에서 팀 오분류 시 원인 분석용.
    """
    mapping = team_mapping_config()
    team_labels = team_labels_from_config(mapping)
    prec = mapping.get("precedence") or []
    team_ids: list[str] = []
    if isinstance(prec, list):
        for row in prec:
            if isinstance(row, dict) and str(row.get("teamId") or "").strip():
                team_ids.append(str(row["teamId"]).strip())
    fb = mapping.get("fallback")
    if isinstance(fb, dict) and str(fb.get("teamId") or "").strip():
        team_ids.append(str(fb["teamId"]).strip())
    else:
        team_ids.append("shared")

    counts: dict[str, int] = {tid: 0 for tid in dict.fromkeys(team_ids)}
    prof_id = profile_id_for_project(project_id)

    for issue in issues:
        sev = severity_key_fn(issue)
        if not is_high_risk_fn(sev):
            continue
        comp = issue_component_key(issue)
        segs = path_segments_for_team_match(comp, project_id)
        tid = team_id_for_path_segments(segs, mapping)
        counts[tid] = counts.get(tid, 0) + 1
        _append_team_match_debug_line(
            {
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "projectId": project_id,
                "moduleProfileId": prof_id,
                "issueKey": str(issue.get("key") or issue.get("issueKey") or ""),
                "component": comp,
                "severity": sev,
                "segments": segs,
                "teamId": tid,
                "teamLabel": team_labels.get(tid, tid),
            }
        )

    return counts


def team_labels_from_config(mapping: dict[str, Any] | None = None) -> dict[str, str]:
    """teamId -> 표시 라벨 (한글)."""
    cfg = mapping if mapping is not None else team_mapping_config()
    out: dict[str, str] = {}
    prec = cfg.get("precedence") or []
    if isinstance(prec, list):
        for row in prec:
            if not isinstance(row, dict):
                continue
            tid = str(row.get("teamId") or "").strip()
            lbl = str(row.get("label") or "").strip()
            if tid:
                out[tid] = lbl or tid
    fb = cfg.get("fallback")
    if isinstance(fb, dict):
        fid = str(fb.get("teamId") or "").strip()
        if fid:
            out[fid] = str(fb.get("label") or "").strip() or fid
    return out


def team_display_order(mapping: dict[str, Any] | None = None) -> list[str]:
    """대시보드 나열 순: precedence 순 + fallback."""
    cfg = mapping if mapping is not None else team_mapping_config()
    order: list[str] = []
    prec = cfg.get("precedence") or []
    if isinstance(prec, list):
        for row in prec:
            if isinstance(row, dict) and str(row.get("teamId") or "").strip():
                order.append(str(row["teamId"]).strip())
    fb = cfg.get("fallback")
    if isinstance(fb, dict) and str(fb.get("teamId") or "").strip():
        fid = str(fb["teamId"]).strip()
        if fid not in order:
            order.append(fid)
    return order
