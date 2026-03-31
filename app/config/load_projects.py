"""프로젝트 목록 — `config/component_projects.json` 단일 출처.

각 행: id, label, componentKey(Sonar), 선택 필드 stack(java|vue) — 운영자가 스택 구분용으로만 사용.
모듈 집계 규칙은 `config/module_grouping.json` 의 projectProfiles[id] 가 단일 출처다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "component_projects.json"


def load_component_projects() -> list[dict[str, Any]]:
    if not _CONFIG_PATH.is_file():
        return []
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return data


def projects_with_keys() -> list[dict[str, Any]]:
    """componentKey 가 비어 있지 않은 항목만."""
    out: list[dict[str, Any]] = []
    for row in load_component_projects():
        key = str(row.get("componentKey") or "").strip()
        if not key:
            continue
        out.append({**row, "componentKey": key})
    return out
