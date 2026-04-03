import json
import logging
from typing import Any, Mapping, Sequence

import httpx

from app.core.config import settings
from app.core.exceptions import SonarConfigError, SonarParseError
from app.services.app_http_log import log_sonar_outgoing_request, log_sonar_response

logger = logging.getLogger(__name__)


class SonarQubeClient:
    def __init__(self) -> None:
        self._base = settings.sonar_base_url.rstrip("/")
        if not self._base:
            raise SonarConfigError("SONAR_BASE_URL is empty after normalization")

    def _client(self) -> httpx.AsyncClient:
        if not settings.sonar_token:
            raise SonarConfigError(
                "SONAR_TOKEN is missing or empty. Set it in .env (project root) or the environment."
            )
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "sonarqube-monitor/0.1",
        }
        auth: httpx.Auth | tuple[str, str] | None = None
        if settings.sonar_auth == "bearer":
            headers["Authorization"] = f"Bearer {settings.sonar_token}"
        else:
            auth = (settings.sonar_token, "")

        proxy = settings.sonar_proxy or None

        return httpx.AsyncClient(
            base_url=self._base,
            auth=auth,
            headers=headers,
            timeout=httpx.Timeout(60.0),
            verify=settings.sonar_ssl_verify,
            follow_redirects=True,
            trust_env=settings.sonar_httpx_trust_env,
            proxy=proxy,
        )

    async def _get(
        self,
        path: str,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    ) -> httpx.Response:
        """FastAPI → Sonar 업스트림 GET. 호출 직전 `log_sonar_outgoing_request` 단일 진입."""
        log_sonar_outgoing_request(method="GET", path=path, params=params)
        async with self._client() as client:
            return await client.get(path, params=params)

    async def issues_search(
        self,
        params: Mapping[str, str] | Sequence[tuple[str, str]],
    ) -> dict:
        r = await self._get("/api/issues/search", params)
        if r.is_error:
            log_sonar_response(
                path="/api/issues/search",
                response=r,
                body_preview=(r.text or "")[:800],
            )
            logger.warning(
                "SonarQube %s %s — %s",
                r.status_code,
                r.request.url,
                (r.text or "")[:800],
            )
            r.raise_for_status()
        data = self._response_json(r, context="issues/search")
        issues = data.get("issues") or []
        paging = data.get("paging") or {}
        total: int | None = None
        if isinstance(paging, dict):
            t = paging.get("total")
            if isinstance(t, int):
                total = t
        log_sonar_response(
            path="/api/issues/search",
            response=r,
            issues_count=len(issues) if isinstance(issues, list) else 0,
            paging_total=total,
        )
        return data

    async def request_status(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, object]:
        """HTTP 코드와 본문(JSON 가능 시 dict)."""
        r = await self._get(path, params or {})
        body: object = r.text
        try:
            body = r.json()
        except json.JSONDecodeError:
            pass
        if r.is_error:
            logger.warning(
                "SonarQube %s %s — %s",
                r.status_code,
                r.request.url,
                (r.text or "")[:800],
            )
        kind = "dict" if isinstance(body, dict) else ("list" if isinstance(body, list) else "text")
        preview: str | None = None
        if settings.http_log_level == "debug":
            if isinstance(body, (dict, list)):
                preview = json.dumps(body, ensure_ascii=False)[:500]
            elif isinstance(body, str):
                preview = body[:500]
        log_sonar_response(
            path=path,
            response=r,
            body_kind=kind,
            body_preview=preview,
        )
        return r.status_code, body

    def _response_json(self, r: httpx.Response, *, context: str) -> dict:
        if not r.content:
            raise SonarParseError(
                f"Empty body from SonarQube ({context})",
                content_type=r.headers.get("content-type"),
                snippet="",
            )
        try:
            data = r.json()
        except json.JSONDecodeError as e:
            snippet = (r.text or "")[:800]
            logger.warning(
                "Non-JSON from SonarQube %s: content-type=%s snippet=%s",
                context,
                r.headers.get("content-type"),
                snippet,
            )
            raise SonarParseError(
                f"SonarQube returned non-JSON ({context})",
                content_type=r.headers.get("content-type"),
                snippet=snippet,
            ) from e
        if not isinstance(data, dict):
            raise SonarParseError(
                f"Expected JSON object from SonarQube ({context}), got {type(data).__name__}",
                content_type=r.headers.get("content-type"),
                snippet=str(data)[:800],
            )
        return data


sonar_client = SonarQubeClient()
