"""
Sonar 업스트림·내부 FastAPI 응답 로깅 (단일 레벨).

`HTTP_LOG_LEVEL` / `SONAR_HTTP_LOG_LEVEL` → `settings.http_log_level` (off / info / debug).
토큰·Authorization 값은 로그하지 않는다.
"""
from __future__ import annotations

import json
import logging
import shlex
import time
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger("app.http")

_http_logging_configured = False


def configure_http_logging() -> None:
    """`app.http` 로거를 콘솔에 연결. uvicorn 루트 로거와 무관하게 INFO 출력."""
    global _http_logging_configured
    if _http_logging_configured:
        return
    _http_logging_configured = True
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _level() -> str:
    return settings.http_log_level


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
    """Sonar 업스트림 호출 직전."""
    level = _level()
    if level == "off":
        return

    m = method.upper()
    full_url = build_sonar_full_url(path=path, params=params)

    if level == "info":
        logger.info("SonarQube → %s %s", m, full_url)
        return

    logger.info("SonarQube → %s %s", m, full_url)
    pairs = _normalize_query_pairs(params)
    if pairs:
        logger.info("SonarQube → query params: %s", pairs)
    if json_body is not None:
        logger.info("SonarQube → JSON body: %s", json_body)
    if settings.sonar_auth == "bearer":
        curl_line = (
            f'curl -sS -H "Authorization: Bearer $SONAR_TOKEN" {shlex.quote(full_url)}'
        )
        logger.info("SonarQube → curl (Bearer, SONAR_TOKEN 사용): %s", curl_line)
    else:
        curl_line = f'curl -sS -u "$SONAR_TOKEN:" {shlex.quote(full_url)}'
        logger.info("SonarQube → curl (Basic, SONAR_TOKEN 사용): %s", curl_line)


def log_sonar_response(
    *,
    path: str,
    response: httpx.Response,
    issues_count: int | None = None,
    paging_total: int | None = None,
    body_kind: str | None = None,
    body_preview: str | None = None,
) -> None:
    """
    Sonar 업스트림 응답 직후. HTTP 레벨 성공/실패 + (가능 시) issues/search 건수.
    """
    level = _level()
    if level == "off":
        return

    ok = not response.is_error
    status = response.status_code
    url = str(response.request.url)

    if level == "info":
        parts = [f"SonarQube ← {status}", "ok" if ok else "error", path]
        if issues_count is not None:
            parts.append(f"issues={issues_count}")
        if paging_total is not None:
            parts.append(f"total={paging_total}")
        if body_kind:
            parts.append(f"body={body_kind}")
        if not ok and body_preview:
            snippet = body_preview.replace("\n", " ").strip()[:160]
            if snippet:
                parts.append(f"snippet={snippet}")
        logger.info(" ".join(parts))
        return

    logger.info("SonarQube ← %s %s %s url=%s", status, "ok" if ok else "error", path, url)
    if issues_count is not None:
        logger.info("SonarQube ← issues_count=%s paging_total=%s", issues_count, paging_total)
    if body_preview:
        logger.info("SonarQube ← body preview: %s", body_preview[:2000])


def _summarize_json_dict(d: dict[str, Any], max_len: int = 400) -> str:
    parts: list[str] = []
    for k in sorted(d.keys())[:24]:
        v = d[k]
        if isinstance(v, list):
            parts.append(f"{k}=[{len(v)}]")
        elif isinstance(v, dict):
            parts.append(f"{k}={{…{len(v)} keys}}")
        elif isinstance(v, (str, int, float, bool)) or v is None:
            s = repr(v) if len(repr(v)) <= 48 else repr(v)[:45] + "…"
            parts.append(f"{k}={s}")
        else:
            parts.append(f"{k}={type(v).__name__}")
    out = " ".join(parts)
    return out if len(out) <= max_len else out[: max_len - 1] + "…"


def summarize_response_body(body: bytes, content_type: str | None) -> str:
    """내부 API 응답 본문 요약 (민감 데이터는 전체 덤프 금지)."""
    ct = (content_type or "").lower()
    if "application/json" not in ct:
        return f"non-json len={len(body)}"
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return f"json len={len(body)}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return f"invalid-json len={len(text)}"
    if isinstance(data, dict):
        return _summarize_json_dict(data)
    if isinstance(data, list):
        return f"array len={len(data)}"
    return type(data).__name__


class InternalApiLogMiddleware(BaseHTTPMiddleware):
    """`/api/*` 요청에 대해 상태 코드·소요 시간·(debug) 본문 요약 로그."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)

        level = _level()
        if level == "off":
            return await call_next(request)

        method = request.method.upper()
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        if level == "info":
            logger.info(
                "API ← %s %s %s %.1fms",
                method,
                path,
                response.status_code,
                duration_ms,
            )
            return response

        # debug: 응답 본문 스트림 소비 후 재구성 (스트리밍 실패 시 본문 요약 생략)
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
        except Exception:
            logger.info(
                "API ← %s %s %s %.1fms (response body not logged)",
                method,
                path,
                response.status_code,
                duration_ms,
            )
            return response

        summary = summarize_response_body(body, response.headers.get("content-type"))
        logger.info(
            "API ← %s %s %s %.1fms %s",
            method,
            path,
            response.status_code,
            duration_ms,
            summary,
        )

        headers = dict(response.headers)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )


# 모듈 로드 시 핸들러 연결 (기존 sonar_http_log 동작 유지)
configure_http_logging()
