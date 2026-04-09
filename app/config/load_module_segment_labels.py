"""`config/module_segment_labels.json` — 표시용 tree + 모듈 집계 제외 규칙."""
from __future__ import annotations

import json
import os
import tempfile
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


def atomic_write_module_segment_labels(data: dict[str, Any]) -> None:
    """UTF-8 JSON, 동일 디렉터리에 임시 파일 후 replace."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".json",
        dir=str(_CONFIG_PATH.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        Path(tmp_name).replace(_CONFIG_PATH)
    except BaseException:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def replace_team_mapping_stored(team_mapping: dict[str, Any]) -> None:
    """
    전체 JSON을 읽어 `teamMapping`만 교체 후 저장.
    기존 `teamMapping._note` 문자열이 있으면 유지(본문에 `_note`가 없을 때).
    """
    if not _CONFIG_PATH.is_file():
        raise FileNotFoundError(str(_CONFIG_PATH))
    data = load_module_segment_labels()
    old_tm = data.get("teamMapping")
    old_note: str | None = None
    if isinstance(old_tm, dict):
        n = old_tm.get("_note")
        if isinstance(n, str) and n.strip():
            old_note = n.strip()
    if "_note" not in team_mapping and old_note is not None:
        team_mapping = {**team_mapping, "_note": old_note}
    data["teamMapping"] = team_mapping
    atomic_write_module_segment_labels(data)


def exclude_rules_for_profile(profile_id: str) -> dict[str, Any]:
    """`maps.<profileId>.exclude` — pathPrefixes·pathContains·pathSegmentAny·… 없으면 빈 dict."""
    data = load_module_segment_labels()
    maps = data.get("maps") or {}
    row = maps.get(profile_id) or {}
    ex = row.get("exclude")
    return ex if isinstance(ex, dict) else {}


def team_mapping_config() -> dict[str, Any]:
    """루트 `teamMapping` — HIGH RISK 팀 집계. 없으면 빈 dict."""
    data = load_module_segment_labels()
    tm = data.get("teamMapping")
    return tm if isinstance(tm, dict) else {}
