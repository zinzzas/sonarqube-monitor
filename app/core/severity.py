"""
플랫폼 표준 Severity: BLOCKER | HIGH | MEDIUM | LOW | INFO

SonarQube Web API는 CRITICAL / MAJOR / MINOR 등을 사용한다.
집계·리포트·저장 시 아래 매핑으로 통일한다.

이슈 객체 단위 집계는 웹 `web/src/severity.js` 의 `resolveIssueSeverityRaw` /
`displaySeverityForIssue` 와 동일 규칙을 쓴다 (최상위 severity 우선, 없으면 impacts).
"""

from __future__ import annotations

from typing import Any

# 표준 레벨 (순서: 높은 위험 → 낮음)
STANDARD_SEVERITIES: tuple[str, ...] = ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO")

# SonarQube `issues/search` 의 `severities` 값 (표준과 인덱스 1:1 — BLOCKER↔BLOCKER, HIGH↔CRITICAL, …)
SONAR_NATIVE_SEVERITY_ORDER: tuple[str, ...] = (
    "BLOCKER",
    "CRITICAL",
    "MAJOR",
    "MINOR",
    "INFO",
)

# SonarQube API 응답 값 → 표준 (web/src/severity.js displaySeverity 와 동일)
FROM_SONAR_API: dict[str, str] = {
    "CRITICAL": "HIGH",
    "MAJOR": "MEDIUM",
    "MINOR": "LOW",
    # BLOCKER, INFO 는 동일
}

# web/src/severity.js SEVERITY_RANK — impacts 병합 시 최강 등급 선택
_SEVERITY_RANK: dict[str, int] = {
    "BLOCKER": 60,
    "CRITICAL": 55,
    "HIGH": 52,
    "MAJOR": 40,
    "MEDIUM": 38,
    "MINOR": 30,
    "LOW": 25,
    "INFO": 10,
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
    up = str(raw).strip().upper()
    return FROM_SONAR_API.get(up, up)


def parse_severity_floor(raw: str | None) -> str:
    """
    `component_projects.json` 의 `severityFloor` 등 — 표준 토큰으로 정규화.
    비어 있거나 알 수 없으면 INFO (필터 없음).
    """
    if raw is None:
        return "INFO"
    s = str(raw).strip().upper()
    if not s:
        return "INFO"
    if s in STANDARD_SEVERITIES:
        return s
    return "INFO"


def sonar_native_severities_for_standard_floor(floor: str) -> tuple[str, ...]:
    """
    표준 하한(floor) 이상만 Sonar API로 조회할 때 사용.
    예: MEDIUM → BLOCKER, CRITICAL, MAJOR (HIGH·BLOCKER 포함).
    """
    f = parse_severity_floor(floor)
    idx = STANDARD_SEVERITIES.index(f)
    return SONAR_NATIVE_SEVERITY_ORDER[: idx + 1]


def _severity_rank(token: str) -> int:
    k = str(token or "").strip().upper()
    return _SEVERITY_RANK.get(k, 0)


def _pick_strongest_severity(raw_strings: list[str]) -> str:
    best = ""
    best_r = -1
    for r in raw_strings:
        if not r or not str(r).strip():
            continue
        u = str(r).strip().upper()
        rr = _severity_rank(u)
        if rr > best_r:
            best_r = rr
            best = u
    return best


def resolve_issue_severity_raw(issue: dict[str, Any] | None) -> str:
    """
    Sonar 이슈에서 심각도 원문 — 웹 `resolveIssueSeverityRaw` 와 동일.
    최상위 `severity` 가 있으면 그대로, 없으면 `impacts[].severity` 중 최고 등급.
    """
    if not issue or not isinstance(issue, dict):
        return ""
    top = issue.get("severity")
    if top is not None and str(top).strip() != "":
        return str(top).strip()
    impacts = issue.get("impacts")
    if not isinstance(impacts, list) or len(impacts) == 0:
        return ""
    from_impacts: list[str] = []
    for x in impacts:
        if isinstance(x, dict):
            sv = x.get("severity")
            if sv is not None and str(sv).strip() != "":
                from_impacts.append(str(sv).strip())
    return _pick_strongest_severity(from_impacts)


def severity_bucket_for_issue(issue: dict[str, Any] | None) -> str:
    """
    집계·내보내기용 표준 버킷 — 웹 `displaySeverityForIssue` 와 동일.
    알 수 없는 값은 INFO 로 귀속 (기존 _severity_key 와 동일).
    """
    raw = resolve_issue_severity_raw(issue)
    up = str(raw).strip().upper()
    if not up:
        return "INFO"
    n = normalize_from_sonar(up)
    if n in STANDARD_SEVERITIES:
        return n
    return "INFO"


def severity_rank_for_sort(issue: dict[str, Any] | None) -> int:
    """로컬 issues/search 정렬 — `resolve_issue_severity_raw` 토큰 기준 수치."""
    raw = resolve_issue_severity_raw(issue)
    return _severity_rank(str(raw).strip().upper())


def to_sonar_severity_param(level: str) -> str:
    """UI·표준 단일 값 → API 쿼리용."""
    return TO_SONAR_API_FILTER.get(level, level)
