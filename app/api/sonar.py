import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.exceptions import SonarConfigError
from app.services.sonarqube_client import sonar_client
from app.services.transport_errors import describe_httpx_request_error

router = APIRouter(tags=["sonar"])


@router.get("/sonar/config")
def sonar_config() -> dict:
    """실제 호출에 쓰는 SonarQube 도메인·연결 옵션(토큰 값은 노출하지 않음)."""
    return {
        "sonar_base_url": settings.sonar_base_url,
        "resolved_issues_example": f"{settings.sonar_base_url}/api/issues/search",
        "sonar_auth": settings.sonar_auth,
        "ssl_verify": settings.sonar_ssl_verify,
        "proxy_configured": bool(settings.sonar_proxy),
        "has_sonar_token": bool(settings.sonar_token),
    }


@router.get("/sonar/diagnostic")
async def sonar_diagnostic(
    component_keys: str = Query("2320-all", alias="componentKeys"),
) -> dict:
    """
    SonarQube 연결 분리 진단.

    - `/api/authentication/validate` → 토큰만 검증(가벼움). `valid:true` 만으로 네트워크·인증은 정상일 수 있음.
    - `/api/issues/search` → 검색 백엔드(Elasticsearch 등) 사용. 여기만 멈추면 **Sonar 서버 측 검색/인덱스** 의심.
    - `/api/system/status` → 인스턴스 상태.

    validate·system 은 빠른데 issues 만 무한 대기/타임아웃이면 클라이언트(Windows·curl) 문제가 아니라 **Sonar 쪽 issues 검색**을 점검하는 편이 맞다.
    """
    out: dict = {
        "sonar_base_url": settings.sonar_base_url,
        "sonar_auth": settings.sonar_auth,
        "ssl_verify": settings.sonar_ssl_verify,
        "proxy_configured": bool(settings.sonar_proxy),
    }

    async def _safe(path: str, params: dict | None = None) -> dict:
        try:
            code, body = await sonar_client.request_status(path, params)
        except SonarConfigError as e:
            raise HTTPException(
                status_code=500,
                detail={"code": "sonar_config", "message": str(e)},
            ) from e
        except httpx.RequestError as e:
            return {
                "http": None,
                "error": "request_failed",
                **describe_httpx_request_error(e, target_url=settings.sonar_base_url),
            }
        return {"http": code, "body": body}

    out["authentication_validate"] = await _safe("/api/authentication/validate")
    out["system_status"] = await _safe("/api/system/status")
    try:
        out["issues_search_probe"] = await asyncio.wait_for(
            _safe(
                "/api/issues/search",
                {"componentKeys": component_keys, "ps": "1"},
            ),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        out["issues_search_probe"] = {
            "http": None,
            "error": "timeout_after_45s",
            "componentKeys": component_keys,
            "hint": "issues/search 가 응답하지 않음 — Sonar 검색(Elasticsearch)·인덱스·부하를 서버 측에서 확인",
        }
    else:
        out["issues_search_probe"]["componentKeys"] = component_keys
    out["read_me"] = (
        "authentication_validate 가 valid 이고 system_status 가 정상인데 issues_search 만 지연·빈 응답·타임아웃이면 "
        "SonarQube 서버의 이슈 인덱스·Elasticsearch(또는 내장 검색) 상태·부하를 확인한다(서버 로그, 관리 UI). "
        "system_status·issues 모두 503 → SonarQube 또는 앞단 LB/WAF, VPN·사내망. "
        "연결 자체가 안 되면 SONAR_PROXY 또는 HTTP_PROXY/HTTPS_PROXY·SONAR_HTTPX_TRUST_ENV 를 점검."
    )
    return out
