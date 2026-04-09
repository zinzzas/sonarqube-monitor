"""`config/module_grouping.json` — 프로젝트별 모듈 경로 추출 프로필.

`projectProfiles`의 키는 `config/component_projects.json`의 각 행 `id`와 동일해야 한다.
행에만 있고 `projectProfiles`에 없으면 `stack`(java|vue)으로 프로필을 보조한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "module_grouping.json"


def load_module_grouping() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {}
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}
