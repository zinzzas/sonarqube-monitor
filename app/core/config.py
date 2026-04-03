from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py → project root (always load .env from repo root, not cwd)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sonar_base_url: str = ""
    """SONAR_BASE_URL — 프로젝트 루트 `.env`에만 정의. 스킴(https://)과 호스트 필수."""
    sonar_token: str = ""
    """User token. Basic: username=token, password empty. Bearer: set sonar_auth=bearer."""
    sonar_auth: Literal["basic", "bearer"] = "basic"
    """SONAR_AUTH=bearer 일부 인스턴스(10.x+)에서 Basic 대신 Bearer 토큰."""
    sonar_ssl_verify: bool = True
    """기업망 SSL 가로채기 시 SONAR_SSL_VERIFY=false (보안상 권장하지 않음)."""
    sonar_proxy: str = ""
    """선택: 사내 프록시 URL (예: http://proxy.company:8080). 비우면 HTTP_PROXY/HTTPS_PROXY 환경 변수 사용."""
    sonar_sample_component_keys: str = ""
    """Optional default for `/api/issues/search` when `componentKeys` is omitted (e.g. project key)."""
    sonar_mirror_issue_statuses: bool = False
    """
    SonarQube 10.4+ 에서 `statuses` 필터가 `issueStatuses` 로 이전된 인스턴스용.
    True 이면 요청에 `statuses`만 있을 때 동일 값을 `issueStatuses` 로 한 번 더 붙여 전달한다.
    """
    http_log_level: Literal["off", "info", "debug"] = Field(
        default="debug",
        validation_alias=AliasChoices("http_log_level", "sonar_http_log_level"),
    )
    """
    Sonar 업스트림 + 내부 `/api/*` 응답 로깅 (동일 레벨).
    환경 변수: `HTTP_LOG_LEVEL` 또는 기존 `SONAR_HTTP_LOG_LEVEL`.
    `off`: 미출력. `info`: 요청/응답 한 줄(상태·건수·소요시간). `debug`: 쿼리·curl·본문 요약.
    """

    metrics_project_cache_ttl_seconds: float = 120.0
    """대시보드 집계 시 프로젝트별 Sonar 이슈 결과 캐시 TTL(초)."""
    metrics_dashboard_cache_ttl_seconds: float = 90.0
    """조합된 `/api/metrics/dashboard` 전체 응답 캐시 TTL(초)."""
    metrics_sonar_max_concurrent: int = 4
    """프로젝트별 `fetch_all_issues` 동시 실행 상한(Sonar 부하 완화)."""

    @field_validator("sonar_base_url", mode="before")
    @classmethod
    def normalize_sonar_base_url(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError(
                "SONAR_BASE_URL이 비어 있습니다. 프로젝트 루트 `.env`에 설정하세요."
            )
        if not isinstance(v, str):
            raise ValueError("SONAR_BASE_URL은 문자열이어야 합니다.")
        s = v.strip().rstrip("/")
        low = s.lower()
        if not low.startswith(("http://", "https://")):
            raise ValueError(
                "SONAR_BASE_URL은 http:// 또는 https:// 로 시작해야 합니다 (호스트 도메인 누락 방지)."
            )
        parsed = urlparse(s)
        if not parsed.netloc:
            raise ValueError(
                "SONAR_BASE_URL에 호스트가 필요합니다. 예: https://sonarqube.example.com"
            )
        return s

    @field_validator("sonar_auth", mode="before")
    @classmethod
    def normalize_auth(cls, v: object) -> str:
        if v is None or v == "":
            return "basic"
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("basic", "bearer"):
                return s
        return "basic"

    @field_validator("sonar_ssl_verify", mode="before")
    @classmethod
    def parse_ssl_verify(cls, v: object) -> bool:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("0", "false", "no", "off"):
                return False
            if s in ("1", "true", "yes", "on"):
                return True
        return bool(v) if v is not None else True

    @field_validator("sonar_token", "sonar_sample_component_keys", "sonar_proxy", mode="before")
    @classmethod
    def strip_optional(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("http_log_level", mode="before")
    @classmethod
    def normalize_http_log_level(cls, v: object) -> str:
        if v is None or v == "":
            return "off"
        if not isinstance(v, str):
            return "off"
        s = v.strip().lower()
        if s in ("off", "none", "0", "false", "no"):
            return "off"
        if s in ("info", "information"):
            return "info"
        if s in ("debug", "verbose", "full"):
            return "debug"
        return "off"


settings = Settings()
