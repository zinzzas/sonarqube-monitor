"""path_tree 프로필: component 경로 → 누적 경로 키(롤업) 목록."""
from __future__ import annotations

import re
from typing import Any


def _norm_slash(s: str) -> str:
    return s.replace("\\", "/").strip()


def _anchor_for_path_match(anchor: str) -> str:
    """
    strip 이후 `rest` 는 선행 슬래시가 없다. 앵커를 `/com/hhi/` 처럼 쓰면 매칭이 실패하므로 제거한다.
    """
    a = _norm_slash(anchor)
    while a.startswith("/"):
        a = a[1:]
    return a


def sonar_relative_path(component: str | None) -> str:
    """
    Sonar 이슈 `component`는 보통 `projectKey:relative/path` 형태다.
    접두를 제거하지 않으면 stripPrefixes·anchorAfter 매칭이 실패해 모듈이 전부 unknown 이 될 수 있다.
    """
    path = _norm_slash(str(component or ""))
    if not path:
        return ""
    if ":" in path:
        path = path.split(":", 1)[1].lstrip("/")
    return path


def _looks_like_file(seg: str) -> bool:
    if not seg or "." not in seg:
        return False
    if "/" in seg:
        return False
    base = seg.rsplit(".", 1)[0]
    return bool(base)


def _drop_leading_src_segments(parts: list[str]) -> list[str]:
    """
    stripPrefixes 로 `src/` 한 번만 제거되면 `src/src/...` 첫 세그먼트가 `src`로 남을 수 있다.
    또한 일부 경로는 `src` 세그먼트가 남아 `src/api/...` 형태로 집계되어 segment_labels 의 `api` 트리와 불일치한다.
    Vue 등에서 `src` 를 소스 루트로 볼 때 선행 `src` 세그먼트를 반복 제거한다.
    """
    out = list(parts)
    while out and out[0].lower() == "src":
        out.pop(0)
    return out


def _strip_prefixes_path(path: str, profile: dict[str, Any]) -> str:
    raw = profile.get("stripPrefixes") or ["src/"]
    if isinstance(raw, str):
        strip_prefixes = [raw]
    else:
        strip_prefixes = list(raw)
    strip_prefixes = [_norm_slash(p) for p in strip_prefixes if p]

    rest: str | None = None
    pl = path.lower()
    for p in sorted(strip_prefixes, key=len, reverse=True):
        pn = p.lower()
        idx = pl.find(pn)
        if idx >= 0:
            rest = path[idx + len(p) :].lstrip("/")
            break
    if rest is None:
        rest = path
    return rest


def rollup_path_after_anchor(component: str | None, profile: dict[str, Any]) -> str | None:
    """
    stripPrefixes 적용 후 anchorAfter 이후 경로 (path_tree 집계·exclude 판정 기준).
    anchorAfter가 비어 있지 않은데 매칭 실패 시 None (unknown 브랜치).
    """
    path = sonar_relative_path(component)
    if not path:
        return ""
    rest = _strip_prefixes_path(path, profile)
    anchor = _anchor_for_path_match(str(profile.get("anchorAfter") or ""))
    if anchor:
        m = re.search(re.escape(anchor), rest, re.IGNORECASE)
        if not m:
            return None
        rest = rest[m.end() :].lstrip("/")
    return rest


def chart_rest_after_anchor(component: str | None, profile: dict[str, Any]) -> str:
    """스택 차트용: chartStackAnchorAfter 또는 anchorAfter 이후 경로."""
    path = sonar_relative_path(component)
    if not path:
        return ""
    rest = _strip_prefixes_path(path, profile)
    if "chartStackAnchorAfter" in profile:
        anchor = _anchor_for_path_match(str(profile.get("chartStackAnchorAfter") or ""))
    else:
        anchor = _anchor_for_path_match(str(profile.get("anchorAfter") or ""))
    if anchor:
        m = re.search(re.escape(anchor), rest, re.IGNORECASE)
        if not m:
            return ""
        rest = rest[m.end() :].lstrip("/")
    return rest


def path_tree_segments(component: str | None, profile: dict[str, Any]) -> list[str]:
    """
    anchor 이후 경로 세그먼트만 (누적 문자열 없음). 팀 매핑·표시용.
    `path_tree_cumulative_keys` 와 동일한 전처리(파일명 제거, src strip, maxDepth).
    """
    rest = rollup_path_after_anchor(component, profile)
    if rest is None or not rest:
        return []

    parts = [x for x in rest.split("/") if x]
    parts = _drop_leading_src_segments(parts)
    while parts and _looks_like_file(parts[-1]):
        parts = parts[:-1]
    if not parts:
        return []

    max_depth = int(profile.get("maxDepth") or 8)
    parts = parts[:max_depth]
    return parts


def strip_only_path_segments(
    component: str | None,
    profile: dict[str, Any],
    *,
    max_depth_override: int | None = None,
) -> list[str]:
    """
    anchor 없이 stripPrefixes만 적용한 경로의 디렉터리 세그먼트.

    `path_tree`에서 anchorAfter(예: /fims/)가 경로에 없어 rollup 이 None이 될 때,
    팀 매칭이 전부 fallback(ETC)으로 가지 않도록 토큰을 얻는 용도.
    max_depth_override 가 있으면 프로필 maxDepth 대신 사용(깊은 경로의 토큰까지 검사).
    """
    path = sonar_relative_path(component)
    if not path:
        return []
    rest = _strip_prefixes_path(path, profile)
    if not rest:
        return []
    parts = [x for x in rest.split("/") if x]
    parts = _drop_leading_src_segments(parts)
    while parts and _looks_like_file(parts[-1]):
        parts = parts[:-1]
    if not parts:
        return []
    if max_depth_override is not None:
        md = max(1, int(max_depth_override))
    else:
        md = int(profile.get("maxDepth") or 8)
    parts = parts[:md]
    return parts


def path_tree_cumulative_keys(component: str | None, profile: dict[str, Any]) -> list[str]:
    """
    이슈가 기여하는 경로 노드 키 (롤업).
    예: atm/annualmonthlyleaveplanaccrual → ["atm", "atm/annualmonthlyleaveplanaccrual"]
    """
    rest = rollup_path_after_anchor(component, profile)
    if rest is None:
        return ["unknown"]
    if not rest:
        return []

    parts = path_tree_segments(component, profile)
    if not parts:
        return []

    out: list[str] = []
    acc: list[str] = []
    for p in parts:
        acc.append(p)
        out.append("/".join(acc))
    return out


def path_tree_leaf_key(component: str | None, profile: dict[str, Any]) -> str:
    keys = path_tree_cumulative_keys(component, profile)
    return keys[-1] if keys else "unknown"


def chart_stack_bucket(component: str | None, profile: dict[str, Any]) -> str:
    """
    스택 막대용: strip 후 chartStackAnchorAfter(없으면 anchorAfter) 다음의 첫 경로 세그먼트만.
    split_after 는 module_extract.chart_stack_bucket 에서 처리.
    """
    rest = chart_rest_after_anchor(component, profile)
    if not rest:
        return "unknown"

    parts = [x for x in rest.split("/") if x]
    parts = _drop_leading_src_segments(parts)
    while parts and _looks_like_file(parts[-1]):
        parts = parts[:-1]
    if not parts:
        return "unknown"
    return parts[0]
