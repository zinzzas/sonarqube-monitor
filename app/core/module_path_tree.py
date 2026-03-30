"""path_tree 프로필: component 경로 → 누적 경로 키(롤업) 목록."""
from __future__ import annotations

import re
from typing import Any


def _norm_slash(s: str) -> str:
    return s.replace("\\", "/").strip()


def _looks_like_file(seg: str) -> bool:
    if not seg or "." not in seg:
        return False
    if "/" in seg:
        return False
    base = seg.rsplit(".", 1)[0]
    return bool(base)


def path_tree_cumulative_keys(component: str | None, profile: dict[str, Any]) -> list[str]:
    """
    이슈가 기여하는 경로 노드 키 (롤업).
    예: atm/annualmonthlyleaveplanaccrual → ["atm", "atm/annualmonthlyleaveplanaccrual"]
    """
    path = _norm_slash(str(component or ""))
    if not path:
        return []

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

    anchor = _norm_slash(str(profile.get("anchorAfter") or ""))
    if anchor:
        m = re.search(re.escape(anchor), rest, re.IGNORECASE)
        if not m:
            return ["unknown"]
        rest = rest[m.end() :].lstrip("/")

    parts = [x for x in rest.split("/") if x]
    while parts and _looks_like_file(parts[-1]):
        parts = parts[:-1]
    if not parts:
        return []

    max_depth = int(profile.get("maxDepth") or 8)
    parts = parts[:max_depth]

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
    path = _norm_slash(str(component or ""))
    if not path:
        return "unknown"

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

    if "chartStackAnchorAfter" in profile:
        anchor = _norm_slash(str(profile.get("chartStackAnchorAfter") or ""))
    else:
        anchor = _norm_slash(str(profile.get("anchorAfter") or ""))
    if anchor:
        m = re.search(re.escape(anchor), rest, re.IGNORECASE)
        if not m:
            return "unknown"
        rest = rest[m.end() :].lstrip("/")

    parts = [x for x in rest.split("/") if x]
    while parts and _looks_like_file(parts[-1]):
        parts = parts[:-1]
    if not parts:
        return "unknown"
    return parts[0]
