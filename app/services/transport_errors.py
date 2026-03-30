"""
httpx RequestError → 사람이 읽을 수 있는 transport_kind / hints.

'All connection attempts failed' 는 보통 ConnectError: DNS·방화벽·VPN·호스트 오타·프록시 미설정 등.
"""
from __future__ import annotations

from typing import Any

import httpx


def describe_httpx_request_error(
    exc: httpx.RequestError,
    *,
    target_url: str,
) -> dict[str, Any]:
    """
    API 응답 detail에 넣을 공통 dict.
    """
    underlying = str(exc.__cause__) if exc.__cause__ is not None else None
    hints: list[str] = []
    transport_kind = "unknown"

    if isinstance(exc, httpx.ProxyError):
        transport_kind = "proxy"
        hints.append(
            "프록시(SONAR_PROXY 또는 환경 변수 HTTP_PROXY/HTTPS_PROXY)에 연결하지 못했습니다. 주소·포트·인증을 확인하세요."
        )
    elif isinstance(exc, httpx.ConnectTimeout):
        transport_kind = "connect_timeout"
        hints.append(
            "연결 시간 초과: 호스트가 느리거나 차단되었을 수 있습니다. VPN·사내망·SONAR_BASE_URL을 확인하세요."
        )
    elif isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout)):
        transport_kind = "io_timeout"
        hints.append("읽기/쓰기 시간 초과: 네트워크 불안정 또는 서버 과부하일 수 있습니다.")
    elif isinstance(exc, httpx.PoolTimeout):
        transport_kind = "pool_timeout"
        hints.append("클라이언트 연결 풀 대기 초과(드묾). 동시 요청 수를 줄이거나 재시도하세요.")
    elif isinstance(exc, httpx.ConnectError):
        transport_kind = "connect"
        hints.append(
            "TCP 연결 실패(메시지: All connection attempts failed 등). "
            "DNS·호스트명 오타, VPN 미연결, 방화벽, 사내망 전용 주소인지 확인하세요."
        )
        hints.append(
            "브라우저에서 SONAR_BASE_URL과 동일 주소가 열리는지, 터미널에서 `curl -vI <SONAR_BASE_URL>` 로 비교해 보세요."
        )
    elif isinstance(exc, httpx.ReadError | httpx.WriteError | httpx.CloseError):
        transport_kind = "socket_io"
        hints.append("연결 후 소켓 오류: 네트워크 끊김·서버 재시작 등을 의심하세요.")
    elif isinstance(exc, httpx.UnsupportedProtocol):
        transport_kind = "unsupported_protocol"
        hints.append("SONAR_BASE_URL은 http:// 또는 https:// 로 시작해야 합니다.")
    elif isinstance(exc, httpx.RemoteProtocolError | httpx.LocalProtocolError):
        transport_kind = "tls_or_http_protocol"
        hints.append(
            "TLS/HTTP 프로토콜 오류 가능. SONAR_SSL_VERIFY, 기업용 SSL 가로채기, 인증서를 확인하세요."
        )
    elif isinstance(exc, httpx.TooManyRedirects):
        transport_kind = "too_many_redirects"
        hints.append("리다이렉트가 과도합니다. SONAR_BASE_URL이 최종 SonarQube 루트인지 확인하세요.")

    if not hints:
        hints.append(
            "SONAR_BASE_URL·VPN·프록시(SONAR_PROXY/HTTP_PROXY)·방화벽을 확인하세요."
        )

    request_url: str | None = None
    try:
        if getattr(exc, "request", None) is not None:
            request_url = str(exc.request.url)
    except Exception:
        pass

    return {
        "transport_kind": transport_kind,
        "message": str(exc),
        "hint": " ".join(hints),
        "hints": hints,
        "target_url": target_url,
        "request_url": request_url,
        "underlying_cause": underlying,
    }
