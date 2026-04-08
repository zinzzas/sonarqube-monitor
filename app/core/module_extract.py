"""Component path → 모듈명. `config/module_grouping.json` 의 strategy 로 확장."""
from __future__ import annotations

from typing import Any

from app.config.load_module_grouping import load_module_grouping
from app.config.load_module_segment_labels import exclude_rules_for_profile
from app.core.module_path_tree import (
    chart_stack_bucket as _chart_stack_bucket_path,
    path_tree_cumulative_keys,
    path_tree_leaf_key,
    rollup_path_after_anchor,
    sonar_relative_path,
)


def _norm_slash(s: str) -> str:
    return s.replace("\\", "/").strip()


def _match_excludes(rest: str, cfg: dict[str, Any]) -> bool:
    """`module_segment_labels.maps.<profile>.exclude` 규칙 (OR)."""
    rest_l = _norm_slash(rest).lower()
    for p in cfg.get("pathPrefixes") or []:
        pn = _norm_slash(str(p)).strip().lower().rstrip("/")
        if not pn:
            continue
        if rest_l == pn or rest_l.startswith(pn + "/"):
            return True
    for sub in cfg.get("pathContains") or []:
        s = str(sub).lower()
        if s and s in rest_l:
            return True
    parts = [x for x in rest_l.split("/") if x]
    seg0 = parts[0] if parts else ""
    for seg in cfg.get("firstSegments") or []:
        if seg and seg0 == str(seg).strip().lower():
            return True
    fname = parts[-1] if parts else ""
    for sfx in cfg.get("fileSuffixes") or []:
        if sfx and fname.endswith(str(sfx).lower()):
            return True
    return False


def is_excluded_from_module_rollup(component: str | None, project_id: str | None) -> bool:
    """
    모듈 롤업·스택 차트에서 제외할 경로인지.
    path_tree: anchorAfter 이후 경로(rollup_path_after_anchor) 기준.
    split_after: Sonar 상대 경로 전체(프로젝트키: 제외) 기준.
    Severity 합계에는 여전히 포함(미노출은 모듈/차트 축만).
    """
    cfg = exclude_rules_for_profile(profile_id_for_project(project_id))
    if not cfg:
        return False
    profile = _profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        rest = rollup_path_after_anchor(component, profile)
        if rest is None:
            return False
        if not rest:
            return False
        return _match_excludes(rest, cfg)
    rest = sonar_relative_path(component)
    if not rest:
        return False
    return _match_excludes(rest, cfg)


def _profile_for_project(project_id: str | None) -> dict:
    cfg = load_module_grouping()
    profiles = cfg.get("profiles") or {}
    default_id = str(cfg.get("defaultProfile") or "vue_src_tree")
    pmap = cfg.get("projectProfiles") or {}
    if project_id and str(project_id) in pmap:
        pid = str(pmap[str(project_id)])
    else:
        pid = default_id
    return profiles.get(pid) or profiles.get(default_id) or {}


def profile_for_project(project_id: str | None) -> dict[str, Any]:
    """`module_grouping.json` 에서 프로젝트별 프로필 dict (strategy, anchor 등)."""
    return _profile_for_project(project_id)


def profile_id_for_project(project_id: str | None) -> str:
    cfg = load_module_grouping()
    default_id = str(cfg.get("defaultProfile") or "vue_src_tree")
    pmap = cfg.get("projectProfiles") or {}
    if project_id and str(project_id) in pmap:
        return str(pmap[str(project_id)])
    return default_id


def module_strategy_for_project(project_id: str | None) -> str:
    profile = _profile_for_project(project_id)
    return str(profile.get("strategy") or "split_after")


def chart_stack_unmapped_bucket(project_id: str | None) -> str:
    """
    앵커 미매칭·경로 부족 등으로 내부 토큰이 'unknown' 일 때 대시보드·CSV에 쓸 축 이름.
    `profiles.<id>.chartStackUnmappedBucket` 가 있으면 우선, 없으면 `defaults.chartStackUnmappedBucket`, 없으면 'unknown'.
    """
    cfg = load_module_grouping()
    profile = _profile_for_project(project_id)
    raw = profile.get("chartStackUnmappedBucket")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    d = cfg.get("defaults") or {}
    raw2 = d.get("chartStackUnmappedBucket")
    if isinstance(raw2, str) and raw2.strip():
        return raw2.strip()
    return "unknown"


def module_bucket_display_key(raw: str | None, project_id: str | None) -> str | None:
    """
    집계·스택·모듈 표에 올릴 키. 내부 분류 실패 토큰 'unknown' 만 표시용 라벨로 치환.
    extract_module 등은 계속 'unknown' 을 반환(팀 매칭 등과 구분).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return raw
    if s == "unknown":
        return chart_stack_unmapped_bucket(project_id)
    return s


def _looks_like_file(seg: str) -> bool:
    if not seg or "." not in seg:
        return False
    if "/" in seg:
        return False
    base = seg.rsplit(".", 1)[0]
    return bool(base)


def split_after_path_segments(component: str | None, profile: dict[str, Any]) -> list[str]:
    """
    split_after 프로필에서 `after` 앵커 이후 경로의 디렉터리 세그먼트 전부(파일명 제외).
    extract_module 이 unknown 일 때도 팀 매칭(any/first)에 쓸 토큰을 얻기 위함.
    """
    path = sonar_relative_path(component)
    if not path:
        return []
    after = str(profile.get("after") or "/fims/")
    idx = path.find(after)
    if idx < 0:
        return []
    rest = path[idx + len(after) :].lstrip("/")
    parts = [p for p in rest.replace("\\", "/").split("/") if p]
    while parts and _looks_like_file(parts[-1]):
        parts = parts[:-1]
    return parts[:32]


def extract_module(
    component: str | None,
    project_id: str | None = None,
    *,
    profile: dict[str, Any] | None = None,
) -> str:
    path = sonar_relative_path(component)
    if not path:
        return "unknown"

    prof = profile if profile is not None else _profile_for_project(project_id)
    strategy = str(prof.get("strategy") or "split_after")

    if strategy == "path_tree":
        return path_tree_leaf_key(component, prof)

    if strategy == "split_after":
        after = str(prof.get("after") or "/fims/")
        seg_idx = int(prof.get("segment_index") or 0)
        idx = path.find(after)
        if idx < 0:
            return "unknown"
        rest = path[idx + len(after) :].lstrip("/")
        parts = [p for p in rest.replace("\\", "/").split("/") if p]
        if seg_idx < len(parts):
            return parts[seg_idx]
        return "unknown"

    return "unknown"


def chart_stack_bucket(component: str | None, project_id: str | None = None) -> str | None:
    """대시보드 스택 막대 1축: path_tree 는 anchor 이후 첫 세그먼트, split_after 는 extract_module. 제외 시 None."""
    if is_excluded_from_module_rollup(component, project_id):
        return None
    profile = _profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        return _chart_stack_bucket_path(component, profile)
    return extract_module(component, project_id)


def extract_path_keys_for_rollup(component: str | None, project_id: str | None = None) -> list[str]:
    """이슈 1건이 기여하는 모듈 키 목록 (path_tree 는 누적, split_after 는 1개). 제외 시 빈 목록."""
    if is_excluded_from_module_rollup(component, project_id):
        return []
    profile = _profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        return path_tree_cumulative_keys(component, profile)
    mod = extract_module(component, project_id)
    return [mod] if mod else ["unknown"]
