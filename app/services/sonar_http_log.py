"""
SonarQube로 나가는 HTTP 요청 로깅 (단일 진입점).

설정 `SONAR_HTTP_LOG_LEVEL`으로 노출 범위를 제어한다 (off / info / debug).
토큰·Authorization 값은 절대 로그하지 않는다.
"""
from __future__ import annotations

import logging
import shlex
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger("sonarqube.http")

_sonar_http_logging_configured = False


def configure_sonar_http_logging() -> None:
    """
    `sonarqube.http` 로거를 콘솔(stderr)에 연결한다.

    기본 루트 로거는 WARNING이라 `logger.info()`가 출력되지 않는다.
    uvicorn/FastAPI와 무관하게 Sonar 업스트림 로그만 INFO로 보낸다.
    """
    global _sonar_http_logging_configured
    if _sonar_http_logging_configured:
        return
    _sonar_http_logging_configured = True
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(levelname)s [%(name)s] %(message)s"),
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _normalize_query_pairs(
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None,
) -> list[tuple[str, str]]:
    if not params:
        return []
    if isinstance(params, Mapping):
        return [(str(k), str(v)) for k, v in params.items()]
    return [(str(k), str(v)) for k, v in params]


def build_sonar_full_url(
    *,
    path: str,
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
) -> str:
    """실제 업스트림과 동일한 쿼리스트링으로 전체 URL을 만든다 (브라우저·curl 테스트용)."""
    base = settings.sonar_base_url.rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    pairs = _normalize_query_pairs(params)
    if not pairs:
        return f"{base}{p}"
    qs = urlencode(pairs, doseq=True)
    return f"{base}{p}?{qs}"


def log_sonar_outgoing_request(
    *,
    method: str,
    path: str,
    params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    json_body: Any | None = None,
) -> None:
    """
    모든 SonarQube 업스트림 호출 직전에 한 번씩 호출한다.

    GET은 Sonar REST에서 일반적이며, 이때 `params`는 쿼리스트링이다.
    `json_body`가 있으면 디버그 레벨에서만 마스킹 없이 출력한다 (민감하면 off 사용).
    """
    level = settings.sonar_http_log_level
    if level == "off":
        return

    m = method.upper()
    full_url = build_sonar_full_url(path=path, params=params)

    if level == "info":
        logger.info("SonarQube → %s %s", m, full_url)
        return

    # debug
    logger.info("SonarQube → %s %s", m, full_url)
    pairs = _normalize_query_pairs(params)
    if pairs:
        logger.info("SonarQube → query params: %s", pairs)
    if json_body is not None:
        logger.info("SonarQube → JSON body: %s", json_body)
    if settings.sonar_auth == "bearer":
        curl_line = (
            f"curl -sS -H \"Authorization: Bearer $SONAR_TOKEN\" {shlex.quote(full_url)}"
        )
        logger.info("SonarQube → curl (Bearer, SONAR_TOKEN 사용): %s", curl_line)
    else:
        curl_line = f"curl -sS -u \"$SONAR_TOKEN:\" {shlex.quote(full_url)}"
        logger.info("SonarQube → curl (Basic, SONAR_TOKEN 사용): %s", curl_line)


configure_sonar_http_logging()
