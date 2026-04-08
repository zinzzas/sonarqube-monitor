"""프로젝트 목록 — `config/component_projects.json` 단일 출처.

각 행: id, label, componentKey(Sonar), 선택 필드 stack(java|vue) — 운영자가 스택 구분용으로만 사용.
선택 필드 severityFloor: BLOCKER | HIGH | MEDIUM | LOW | INFO — 해당 레벨 이상만 집계·이슈 목록에 반영
(미지정 시 단일 프로젝트 집계는 INFO=전체, projectId=all 병합은 MEDIUM=기존 B·H·M과 동일).
모듈 집계 규칙은 `config/module_grouping.json` 의 projectProfiles[id] 가 단일 출처다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.severity import parse_severity_floor

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


def project_row_by_component_key(component_key: str) -> dict[str, Any] | None:
    """
    Sonar `componentKeys` 단일 값과 일치하는 `component_projects.json` 행.
    이슈 스냅샷(프로젝트 id) 조회에 사용.
    """
    ck = str(component_key or "").strip()
    if not ck:
        return None
    for row in load_component_projects():
        if str(row.get("componentKey") or "").strip() == ck:
            return row
    return None


def project_labels_map() -> dict[str, str]:
    """대시보드·API 응답 표시용 라벨 — `component_projects.json`의 id → label 단일 출처."""
    out: dict[str, str] = {}
    for row in load_component_projects():
        pid = str(row.get("id") or "").strip()
        if not pid:
            continue
        lab = str(row.get("label") or "").strip()
        out[pid] = lab or pid
    return out


def severity_floor_for_full_metrics(row: dict[str, Any]) -> str:
    """
    단일 프로젝트·엑셀 등 OPEN 전량 수집용 하한.
    `severityFloor` 미지정 시 INFO (Sonar 전 심각도).
    """
    raw = row.get("severityFloor")
    if raw is None or str(raw).strip() == "":
        return "INFO"
    return parse_severity_floor(str(raw))


def severity_floor_for_aggregate_scope(row: dict[str, Any]) -> str:
    """
    `projectId=all` 병합 집계용 하한.
    미지정 시 MEDIUM — 기존 B·H·M(BLOCKER/CRITICAL/MAJOR)만 수집과 동일.
    """
    raw = row.get("severityFloor")
    if raw is None or str(raw).strip() == "":
        return "MEDIUM"
    return parse_severity_floor(str(raw))
