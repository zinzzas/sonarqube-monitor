"""Component path → 모듈명. `config/module_grouping.json` 의 strategy 로 확장."""
from __future__ import annotations

from app.config.load_module_grouping import load_module_grouping
from app.core.module_path_tree import (
    chart_stack_bucket as _chart_stack_bucket_path,
    path_tree_cumulative_keys,
    path_tree_leaf_key,
)


def _profile_for_project(project_id: str | None) -> dict:
    cfg = load_module_grouping()
    profiles = cfg.get("profiles") or {}
    default_id = str(cfg.get("defaultProfile") or "java_fims")
    pmap = cfg.get("projectProfiles") or {}
    if project_id and str(project_id) in pmap:
        pid = str(pmap[str(project_id)])
    else:
        pid = default_id
    return profiles.get(pid) or profiles.get(default_id) or {}


def profile_id_for_project(project_id: str | None) -> str:
    cfg = load_module_grouping()
    default_id = str(cfg.get("defaultProfile") or "java_fims")
    pmap = cfg.get("projectProfiles") or {}
    if project_id and str(project_id) in pmap:
        return str(pmap[str(project_id)])
    return default_id


def module_strategy_for_project(project_id: str | None) -> str:
    profile = _profile_for_project(project_id)
    return str(profile.get("strategy") or "split_after")


def extract_module(component: str | None, project_id: str | None = None) -> str:
    path = str(component or "").strip()
    if not path:
        return "unknown"

    profile = _profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")

    if strategy == "path_tree":
        return path_tree_leaf_key(component, profile)

    if strategy == "split_after":
        after = str(profile.get("after") or "/fims/")
        seg_idx = int(profile.get("segment_index") or 0)
        idx = path.find(after)
        if idx < 0:
            return "unknown"
        rest = path[idx + len(after) :].lstrip("/")
        parts = [p for p in rest.replace("\\", "/").split("/") if p]
        if seg_idx < len(parts):
            return parts[seg_idx]
        return "unknown"

    return "unknown"


def chart_stack_bucket(component: str | None, project_id: str | None = None) -> str:
    """대시보드 스택 막대 1축: path_tree 는 anchor 이후 첫 세그먼트, split_after 는 extract_module."""
    profile = _profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        return _chart_stack_bucket_path(component, profile)
    return extract_module(component, project_id)


def extract_path_keys_for_rollup(component: str | None, project_id: str | None = None) -> list[str]:
    """이슈 1건이 기여하는 모듈 키 목록 (path_tree 는 누적, split_after 는 1개)."""
    profile = _profile_for_project(project_id)
    strategy = str(profile.get("strategy") or "split_after")
    if strategy == "path_tree":
        return path_tree_cumulative_keys(component, profile)
    mod = extract_module(component, project_id)
    return [mod] if mod else ["unknown"]
