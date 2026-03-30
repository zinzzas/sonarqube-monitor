from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py → project root (always load .env from repo root, not cwd)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sonar_base_url: str = "https://sonarqube.devops.cj.net"
    """SONAR_BASE_URL — 스킴(https://)과 호스트 필수. 비우면 룰셋 기본 도메인 사용."""
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

    @field_validator("sonar_base_url", mode="before")
    @classmethod
    def normalize_sonar_base_url(cls, v: object) -> str:
        default = "https://sonarqube.devops.cj.net"
        if v is None:
            return default
        if not isinstance(v, str):
            return default
        s = v.strip().rstrip("/")
        if not s:
            return default
        low = s.lower()
        if not low.startswith(("http://", "https://")):
            raise ValueError(
                "SONAR_BASE_URL must start with http:// or https:// (호스트 도메인 누락 방지)"
            )
        parsed = urlparse(s)
        if not parsed.netloc:
            raise ValueError(
                "SONAR_BASE_URL must include a host, e.g. https://sonarqube.devops.cj.net"
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


settings = Settings()
