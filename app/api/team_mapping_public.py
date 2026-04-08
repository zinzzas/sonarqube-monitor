"""팀 매핑 읽기 전용 — 이슈 목록 클라이언트 필터가 서버 집계와 동일 규칙을 쓰도록."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config.load_module_segment_labels import team_mapping_config

router = APIRouter(tags=["config"])


@router.get("/config/team-mapping")
def get_team_mapping_public() -> dict[str, Any]:
    """인증 없음. `teamIdForIssue`·스냅샷 `teamId` 필터와 동일 출처(`team_mapping_config`)."""
    return {"teamMapping": team_mapping_config()}
