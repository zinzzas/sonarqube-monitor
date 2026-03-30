"""`config/module_grouping.json` — 프로젝트별 모듈 경로 추출 프로필."""
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
