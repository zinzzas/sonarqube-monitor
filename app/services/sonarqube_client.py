import json
import logging
from typing import Any, Mapping, Sequence

import httpx

from app.core.config import settings
from app.core.exceptions import SonarConfigError, SonarParseError
from app.services.sonar_http_log import log_sonar_outgoing_request

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
            trust_env=True,
            proxy=proxy,
        )

    async def issues_search(
        self,
        params: Mapping[str, str] | Sequence[tuple[str, str]],
    ) -> dict:
        log_sonar_outgoing_request(method="GET", path="/api/issues/search", params=params)
        async with self._client() as client:
            r = await client.get("/api/issues/search", params=params)
            if r.is_error:
                logger.warning(
                    "SonarQube %s %s — %s",
                    r.status_code,
                    r.request.url,
                    (r.text or "")[:800],
                )
            r.raise_for_status()
            return self._response_json(r, context="issues/search")

    async def request_status(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, object]:
        """HTTP 코드와 본문(JSON 가능 시 dict)."""
        log_sonar_outgoing_request(method="GET", path=path, params=params or {})
        async with self._client() as client:
            r = await client.get(path, params=params or {})
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
