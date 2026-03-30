"""
플랫폼 표준 Severity: BLOCKER | HIGH | MEDIUM | LOW | INFO

SonarQube Web API는 CRITICAL / MAJOR / MINOR 등을 사용한다.
집계·리포트·저장 시 아래 매핑으로 통일한다.
"""

from __future__ import annotations

# 표준 레벨 (순서: 높은 위험 → 낮음)
STANDARD_SEVERITIES: tuple[str, ...] = ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")

# SonarQube API 응답 값 → 표준
FROM_SONAR_API: dict[str, str] = {
    "CRITICAL": "HIGH",
    "MAJOR": "MEDIUM",
    "MINOR": "LOW",
    # BLOCKER, INFO 는 동일
}

# 표준 → SonarQube `severities` 필터 파라미터 값 (역검색용)
TO_SONAR_API_FILTER: dict[str, str] = {
    "HIGH": "CRITICAL",
    "MEDIUM": "MAJOR",
    "LOW": "MINOR",
}


def normalize_from_sonar(raw: str | None) -> str:
    if not raw:
        return ""
    return FROM_SONAR_API.get(raw, raw)


def to_sonar_severity_param(level: str) -> str:
    """UI·표준 단일 값 → API 쿼리용."""
    return TO_SONAR_API_FILTER.get(level, level)
