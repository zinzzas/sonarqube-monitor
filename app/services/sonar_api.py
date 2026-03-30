"""
SonarQube API 프록시: 쿼리 수집·업스트림 호출·오류를 HTTP 응답으로 매핑.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.exceptions import SonarConfigError, SonarParseError
from app.services.sonarqube_client import sonar_client
from app.services.transport_errors import describe_httpx_request_error

logger = logging.getLogger(__name__)


def collect_issues_search_params(request: Request) -> list[tuple[str, str]]:
    """
    쿼리스트링을 (키, 값) 목록으로 유지해 업스트림에 그대로 전달한다.
    dict 로 줄이면 동일 키가 덮어씌워질 수 있어 multi_items() 순서·중복을 보존한다.
    """
    pairs = list(request.query_params.multi_items())
    keys_present = {k for k, _ in pairs}
    if "componentKeys" not in keys_present:
        default = settings.sonar_sample_component_keys.strip()
        if default:
            pairs.append(("componentKeys", default))
            keys_present.add("componentKeys")
    if "componentKeys" not in keys_present:
        raise HTTPException(
            status_code=400,
            detail="Missing componentKeys. Pass ?componentKeys=<projectKey> or set SONAR_SAMPLE_COMPONENT_KEYS in .env",
        )
    if settings.sonar_mirror_issue_statuses and "issueStatuses" not in keys_present:
        for k, v in pairs:
            if k == "statuses" and v:
                pairs.append(("issueStatuses", v))
                break
    return pairs


def _http_status_error_to_http_exception(e: httpx.HTTPStatusError) -> HTTPException:
    body: object = e.response.text
    try:
        body = e.response.json()
    except json.JSONDecodeError:
        pass
    status = e.response.status_code
    detail: dict[str, Any] = {
        "upstream_status": status,
        "upstream_body": body,
    }
    if status == 503:
        detail["hint"] = (
            "503은 SonarQube(또는 앞단 LB/WAF) 응답입니다. "
            "VPN·사내망, SonarQube 가용성을 확인하고 SONAR_AUTH=bearer 를 시도하세요. "
            "componentKeys에는 프로젝트 키만 넣으세요."
        )
    elif status == 401:
        detail["hint"] = (
            "401: 토큰 거부. SONAR_TOKEN 또는 SONAR_AUTH=bearer 를 확인하세요."
        )
    return HTTPException(status_code=status, detail=detail)


async def proxy_issues_search(params: dict[str, str]) -> dict:
    """SonarQube issues/search 결과 dict 또는 HTTPException."""
    try:
        return await sonar_client.issues_search(params)
    except SonarConfigError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "sonar_config",
                "message": str(e),
                "where": "프로젝트 루트의 `.env` 파일 ( `main.py` 과 같은 디렉터리 )",
                "how": "한 줄 추가: SONAR_TOKEN=발급받은_토큰값",
                "hint": "저장 후 서버(uvicorn)를 재시작하세요. 토큰은 SonarQube 웹 → 계정 → My Account → Security 에서 발급합니다.",
            },
        ) from e
    except SonarParseError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_not_json",
                "message": str(e),
                "content_type": e.content_type,
                "body_snippet": e.snippet[:800] if e.snippet else None,
                "hint": "SonarQube가 JSON이 아닌 응답(로그인 HTML·프록시 에러 페이지 등)을 돌렸을 수 있습니다.",
            },
        ) from e
    except httpx.HTTPStatusError as e:
        raise _http_status_error_to_http_exception(e) from e
    except httpx.RequestError as e:
        logger.warning(
            "SonarQube transport error [%s]: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        transport = describe_httpx_request_error(e, target_url=settings.sonar_base_url)
        raise HTTPException(
            status_code=502,
            detail={
                "code": "upstream_unreachable",
                **transport,
            },
        ) from e
