"""HIGH RISK 팀 매핑(`teamMapping`) 조회·저장 — `config/module_segment_labels.json`."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
import app.config.load_module_segment_labels as msl
from app.core.config import settings
from app.schemas.team_mapping_admin import TeamMappingUpdate
from app.services.metrics_service import invalidate_dashboard_cache

router = APIRouter(tags=["admin"])


def _require_admin_bearer(authorization: str | None = Header(None)) -> None:
    expected = (settings.admin_team_mapping_token or "").strip()
    if not expected:
        return
    if not authorization or not str(authorization).strip():
        raise HTTPException(
            status_code=401,
            detail="관리 API: Authorization Bearer 토큰이 필요합니다.",
        )
    parts = str(authorization).strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="관리 API: Authorization Bearer 토큰이 필요합니다.",
        )
    got = parts[1].strip()
    if got != expected:
        raise HTTPException(status_code=403, detail="관리 토큰이 올바르지 않습니다.")


@router.get(
    "/admin/team-mapping",
    dependencies=[Depends(_require_admin_bearer)],
)
def get_team_mapping() -> dict[str, Any]:
    if not msl._CONFIG_PATH.is_file():
        raise HTTPException(status_code=404, detail="module_segment_labels.json 이 없습니다.")
    data = msl.load_module_segment_labels()
    tm = data.get("teamMapping")
    if not isinstance(tm, dict):
        raise HTTPException(status_code=500, detail="teamMapping 형식이 올바르지 않습니다.")
    return {"teamMapping": tm}


@router.put(
    "/admin/team-mapping",
    dependencies=[Depends(_require_admin_bearer)],
)
def put_team_mapping(body: TeamMappingUpdate) -> dict[str, Any]:
    if not msl._CONFIG_PATH.is_file():
        raise HTTPException(status_code=404, detail="module_segment_labels.json 이 없습니다.")
    data = msl.load_module_segment_labels()
    old_tm = data.get("teamMapping")
    old_note: str | None = None
    if isinstance(old_tm, dict):
        n = old_tm.get("_note")
        if isinstance(n, str) and n.strip():
            old_note = n.strip()
    try:
        stored = body.to_stored_dict(existing_note=old_note)
        msl.replace_team_mapping_stored(stored)
        invalidate_dashboard_cache()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="module_segment_labels.json 이 없습니다.") from None
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {e}") from e
    return {"ok": True, "teamMapping": stored}


@router.post(
    "/admin/invalidate-cache",
    dependencies=[Depends(_require_admin_bearer)],
)
def post_invalidate_cache() -> dict[str, Any]:
    """
    메모리 집계 캐시 + 이슈 스냅샷 디렉터리 제거 — 팀 매핑 저장과 동일한 무효화.
    `component_projects.json` 의 severityFloor 등을 바꾼 뒤에도 호출하면 다음 요청이 Sonar 기준으로 다시 채움.
    """
    invalidate_dashboard_cache()
    return {"ok": True}
