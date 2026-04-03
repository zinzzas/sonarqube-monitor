"""`config/module_segment_labels.json` — 표시용 tree + 모듈 집계 제외 규칙."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "module_segment_labels.json"


def load_module_segment_labels() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {}
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def exclude_rules_for_profile(profile_id: str) -> dict[str, Any]:
    """`maps.<profileId>.exclude` — 없으면 빈 dict."""
    data = load_module_segment_labels()
    maps = data.get("maps") or {}
    row = maps.get(profile_id) or {}
    ex = row.get("exclude")
    return ex if isinstance(ex, dict) else {}
