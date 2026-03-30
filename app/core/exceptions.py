"""도메인 예외 — 라우터에서 HTTP 상태로 매핑한다."""


class SonarConfigError(Exception):
    """SONAR_TOKEN 누락 등 로컬 설정 문제."""


class SonarParseError(Exception):
    """업스트림 본문이 기대한 JSON이 아님."""

    def __init__(self, message: str, *, content_type: str | None = None, snippet: str = "") -> None:
        super().__init__(message)
        self.content_type = content_type
        self.snippet = snippet
