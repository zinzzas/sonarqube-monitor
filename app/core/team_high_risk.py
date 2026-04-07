"""HIGH RISK(BLOCKER+HIGH) 이슈를 `module_segment_labels.json` 의 teamMapping 으로 버킷."""
from __future__ import annotations

from typing import Any

from app.config.load_module_segment_labels import team_mapping_config
from app.core.module_extract import (
    extract_module,
    profile_for_project,
    split_after_path_segments,
)
from app.core.module_path_tree import path_tree_segments, strip_only_path_segments

# 팀 매칭 fallback 시 경로 깊이(anchor 미매칭·split_after unknown 등) — 프로필 maxDepth(예: 2)보다 넓게 토큰 검사
_TEAM_MATCH_MAX_DEPTH = 32


def _norm_seg(s: str) -> str:
    return str(s or "").strip().lower()


def _path_segments_for_issue(component: str | None, project_id: str | None) -> list[str]:
    """path_tree / split_after 모두 지원. 모듈 exclude 와 무관하게 경로만 사용."""
    profile = profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        segs = path_tree_segments(component, profile)
        if segs:
            return segs
        # anchorAfter(예: /fims/) 가 경로에 없으면 rollup 이 비어 전부 ETC 가 되는 것을 방지
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


def _when_str_list(when: dict[str, Any], key: str, legacy_key: str) -> list[Any]:
    v = when.get(key)
    if v is None:
        v = when.get(legacy_key)
    return v if isinstance(v, list) else []


def _norm_module_list(raw: list[Any]) -> list[str]:
    return [_norm_seg(x) for x in raw if x]


def _match_when(segments: list[str], when: dict[str, Any]) -> bool:
    if not when:
        return False
    seg_l = [_norm_seg(s) for s in segments if s]
    if not seg_l:
        return False

    # 신규: { "modules": [...], "match": "first"|"any" }
    if "modules" in when and isinstance(when.get("modules"), list):
        mods = _norm_module_list(when["modules"])
        mk = str(when.get("match") or "").strip().lower()
        if mods and mk == "first":
            return seg_l[0] in mods
        if mods and mk == "any":
            return any(s in mods for s in seg_l)
        if mods:
            return False
        # modules 가 비어 있으면 아래 구형 키로 폴백

    # 구형: firstModule/anyModule 또는 firstSegment/anySegment (둘 다 있으면 OR)
    fs = _norm_module_list(_when_str_list(when, "firstModule", "firstSegment"))
    anys = _norm_module_list(_when_str_list(when, "anyModule", "anySegment"))
    if fs and not anys:
        return seg_l[0] in fs
    if anys and not fs:
        return any(s in anys for s in seg_l)
    if fs and anys:
        return seg_l[0] in fs or any(s in anys for s in seg_l)
    return False


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
    BLOCKER/HIGH 이슈만 카운트, 이슈당 1버킷.
    severity_key_fn: 이슈 dict -> BLOCKER|HIGH|... (표준 버킷)
    is_high_risk_fn: severity str -> bool
    """
    mapping = team_mapping_config()
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

    for issue in issues:
        sev = severity_key_fn(issue)
        if not is_high_risk_fn(sev):
            continue
        comp = issue.get("component")
        segs = _path_segments_for_issue(comp, project_id)
        tid = team_id_for_path_segments(segs, mapping)
        counts[tid] = counts.get(tid, 0) + 1

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
