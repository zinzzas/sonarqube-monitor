"""
대시보드 집계용 Sonar 이슈 스냅샷 — 프로젝트별 JSON 파일.

- `metrics_project_cache_ttl_seconds` 와 동일한 TTL 기준으로 신선도 판단.
- `full` / `bhm` 블록마다 `severityFloor`(표준 토큰) 저장 — `component_projects.json` 의 하한이 바뀌면
  TTL 안이라도 스냅샷을 쓰지 않고 Sonar 재수집(수동 무효화 없이 정합 유지).
- `invalidate_dashboard_cache` 시 전부 삭제 → 기존 동작(무효화 후 Sonar 재조회) 유지.
"""
from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Literal

from app.core.config import settings
from app.core.severity import parse_severity_floor

logger = logging.getLogger(__name__)

Kind = Literal["full", "bhm"]


def _safe_segment(project_id: str) -> str:
    s = str(project_id or "").strip().replace("..", "").replace("/", "_").replace("\\", "_")
    return s or "_empty"


def project_dir(project_id: str) -> Path:
    return Path(settings.issue_snapshot_dir) / _safe_segment(project_id)


def manifest_path(project_id: str) -> Path:
    return project_dir(project_id) / "manifest.json"


def issues_file(project_id: str, kind: Kind) -> Path:
    name = "issues_full.json" if kind == "full" else "issues_bhm.json"
    return project_dir(project_id) / name


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    tmp.replace(path)


def _manifest_severity_floor_matches(block: dict[str, Any], expected_severity_floor: str) -> bool:
    """manifest 블록의 `severityFloor` 가 현재 설정과 같은 표준 토큰인지. 키 없음·구형 스냅샷은 False."""
    if "severityFloor" not in block:
        return False
    raw = block.get("severityFloor")
    if not isinstance(raw, str) or not raw.strip():
        return False
    return parse_severity_floor(raw) == parse_severity_floor(expected_severity_floor)


def load_issues_if_fresh(
    project_id: str,
    kind: Kind,
    ttl_seconds: float,
    now: float,
    *,
    expected_severity_floor: str,
) -> list[dict[str, Any]] | None:
    """
    스냅샷이 있고 TTL 이내이며 `severityFloor` 가 `expected_severity_floor` 와 일치하면 이슈 목록, 아니면 None.

    `full` 집계는 `severity_floor_for_full_metrics`, `bhm` 은 `severity_floor_for_aggregate_scope` 와 동일 토큰을 넘긴다.
    """
    mpath = manifest_path(project_id)
    if not mpath.is_file():
        return None
    try:
        with open(mpath, encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    key = "full" if kind == "full" else "bhm"
    block = manifest.get(key)
    if not isinstance(block, dict):
        return None
    if not _manifest_severity_floor_matches(block, expected_severity_floor):
        return None
    ts = block.get("savedAt")
    if not isinstance(ts, (int, float)):
        return None
    if (now - float(ts)) >= ttl_seconds:
        return None
    ipath = issues_file(project_id, kind)
    if not ipath.is_file():
        return None
    try:
        with open(ipath, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, list):
        return None
    return raw


def save_issues(
    project_id: str,
    kind: Kind,
    issues: list[dict[str, Any]],
    component_key: str,
    *,
    severity_floor: str,
) -> None:
    """이슈 배열과 manifest 갱신(원자적 파일 교체). `severity_floor` 는 집계 시 사용한 하한과 동일한 값."""
    saved_at = time.time()
    floor_token = parse_severity_floor(severity_floor)
    ipath = issues_file(project_id, kind)
    _atomic_write_json(ipath, issues)
    mpath = manifest_path(project_id)
    data: dict[str, Any] = {}
    if mpath.is_file():
        try:
            with open(mpath, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
    key = "full" if kind == "full" else "bhm"
    data[key] = {
        "savedAt": saved_at,
        "componentKey": str(component_key or "").strip(),
        "issueCount": len(issues),
        "severityFloor": floor_token,
    }
    _atomic_write_json(mpath, data)


def clear_all_snapshots() -> None:
    """팀 매핑 무효화 등 — 스냅샷 제거 후 다음 집계는 Sonar 재조회(기존과 동일)."""
    root = Path(settings.issue_snapshot_dir)
    if not root.is_dir():
        return
    try:
        shutil.rmtree(root)
    except OSError as e:
        logger.warning("issue snapshot rmtree failed: %s", e)
        return
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("issue snapshot mkdir failed: %s", e)


def prune_orphan_dirs(valid_project_ids: set[str]) -> None:
    """component_projects 에 없는 프로젝트 폴더 정리."""
    root = Path(settings.issue_snapshot_dir)
    if not root.is_dir():
        return
    for child in root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name not in valid_project_ids:
            try:
                shutil.rmtree(child)
            except OSError as e:
                logger.warning("prune orphan snapshot %s: %s", child, e)
