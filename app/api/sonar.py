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
    SonarQube 연결 분리 진단: `/api/system/status` vs `/api/issues/search?ps=1`.
    둘 다 503이면 서버/LB/VPN 쪽, system만 200·issues만 503이면 검색·ES 쪽 이슈 가능성이 큼.
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

    out["system_status"] = await _safe("/api/system/status")
    out["issues_search_probe"] = await _safe(
        "/api/issues/search",
        {"componentKeys": component_keys, "ps": "1"},
    )
    out["issues_search_probe"]["componentKeys"] = component_keys
    out["read_me"] = (
        "system_status·issues 모두 503 → SonarQube 또는 앞단 LB/WAF, VPN·사내망 확인. "
        "system은 200인데 issues만 503 → SonarQube 검색/Elasticsearch 측. "
        "연결 자체가 안 되면 SONAR_PROXY 또는 HTTP_PROXY/HTTPS_PROXY 환경 변수를 설정."
    )
    return out
