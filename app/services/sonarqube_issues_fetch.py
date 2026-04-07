"""
SonarQube `GET /api/issues/search` 전량 수집 (OPEN).

## 분석 (플랫폼 엔지니어)
- Sonar는 ElasticSearch 기반으로 **동일 필터에서 인덱스 10,000건을 넘는 페이지 요청을 허용하지 않음**
  (대표 오류: "Can return only the first 10000 results").
- 따라서 `p`만 증가시키는 방식으로는 **11,000번째 이슈를 절대 가져올 수 없음**. `hasNext`가 참이어도
  **같은 쿼리로는** 한계를 넘을 수 없음.

## 설계 (백엔드)
0. **선행 프로브**: 별도 “카운트 API”는 없고, `issues/search` 응답의 `paging.total`이 총건이다. `ps=1`·`p=1`로
   한 번만 호출해 total을 읽으면, 10k 초과 시 **첫 대량 페이지(수백 건)를 가져왔다가 버리는 낭비**를 막는다.
1. **total ≤ 10,000** (또는 total 미상이지만 `p*ps ≤ 10,000` 안에서 끝남): 단일 쿼리로 순차 페이징.
2. **total > 10,000** 또는 **페이지 상한에 도달했는데 아직 더 있음**: 쿼리를 **쪼갬**.
   - 1차: Sonar 네이티브 **severity** 단위(BLOCKER, CRITICAL, MAJOR, MINOR, INFO)로 각각 전량 수집 후 `key`로 병합.
   - 2차: 특정 severity만 10,000 초과면 **createdAfter / createdBefore** 구간을 이진으로 쪼개 재귀(경계는 dedupe).

## 엣지
- 하루 구간에도 10,000 초과면 경고 로그 후 해당 구간은 **최대 10,000건만** 수집(데이터 손실 가능, 극히 드묾).
- 날짜 샤딩 상한은 **고정 미래 연도(2038 등)를 쓰지 않는다.** Sonar는 `createdAfter`가 **현재 시각 이후**이면 400
  (`Start bound cannot be in the future`) 를 반환한다. 상한은 **UTC 기준 내일 0시**(createdBefore 전용)로 맞춘다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.core.severity import (
    parse_severity_floor,
    sonar_native_severities_for_standard_floor,
)
from app.services.sonarqube_client import sonar_client

logger = logging.getLogger(__name__)

# SonarQube issues/search — 동일 쿼리에서 조회 가능한 상한(문서화된 제약)
SONAR_ISSUES_MAX_RESULTS = 10_000
# total만 알기 위한 프로브 — 본 수집 `ps`와 별도(대역폭·불필요한 첫 페이지 폐기 방지)
PROBE_PAGE_SIZE = 1

# API 필터 값 (Sonar 네이티브 이름) — `app.core.severity.SONAR_NATIVE_SEVERITY_ORDER` 와 동일
SONAR_SEVERITY_FILTERS: tuple[str, ...] = (
    "BLOCKER",
    "CRITICAL",
    "MAJOR",
    "MINOR",
    "INFO",
)


def _extra_for_allowed(allowed: tuple[str, ...]) -> dict[str, str]:
    """전 심각도면 파라미터 생략(Sonar OPEN 전체와 동일). 그 외는 콤마 구분 `severities`."""
    if allowed == SONAR_SEVERITY_FILTERS:
        return {}
    return {"severities": ",".join(allowed)}

_RANGE_START = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _utc_tomorrow_start() -> datetime:
    """
    issues/search 의 createdBefore 는 통상 exclusive 날짜 문자열.
    상한을 '내일 00:00 UTC'로 두면 오늘까지의 이슈만 포함되고, 미래 구간 요청을 막는다.
    """
    now = datetime.now(timezone.utc)
    d = now.date() + timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _max_page_index(page_size: int) -> int:
    """`p * ps <= 10_000` 을 만족하는 최대 페이지 번호(1-based)."""
    if page_size <= 0:
        return 1
    return max(1, SONAR_ISSUES_MAX_RESULTS // page_size)


def _iso_date_utc(d: datetime) -> str:
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _search_params(
    component_key: str,
    page: int,
    extra: dict[str, str] | None = None,
    *,
    page_size: int | None = None,
) -> dict[str, str]:
    ps = page_size if page_size is not None else settings.sonar_issues_page_size
    params: dict[str, str] = {
        "componentKeys": component_key,
        "ps": str(ps),
        "p": str(page),
        "statuses": "OPEN",
    }
    if settings.sonar_mirror_issue_statuses:
        params["issueStatuses"] = "OPEN"
    if extra:
        params.update(extra)
    return params


def _dedupe_by_key(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for issue in issues:
        k = issue.get("key")
        if isinstance(k, str) and k:
            merged[k] = issue
    return list(merged.values())


def _paging_total(data: dict[str, Any]) -> int | None:
    paging = data.get("paging") or {}
    if not isinstance(paging, dict):
        return None
    t = paging.get("total")
    return int(t) if isinstance(t, int) else None


async def _sleep_between_pages() -> None:
    delay_s = settings.sonar_issues_page_delay_ms / 1000.0
    if delay_s > 0:
        await asyncio.sleep(delay_s)


async def _fetch_pages_linear(
    component_key: str,
    extra: dict[str, str],
    *,
    first_page: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """
    단일 필터로 페이징. 반환 (이슈 목록, cap_hit).
    cap_hit=True 이면 Sonar 페이지 상한까지 갔는데 마지막 배치가 full → 더 있을 수 있음.
    """
    ps = settings.sonar_issues_page_size
    max_p = _max_page_index(ps)

    if first_page is not None:
        data = first_page
        start_p = 1
    else:
        data = await sonar_client.issues_search(_search_params(component_key, 1, extra))
        start_p = 1

    batch = list(data.get("issues") or [])
    out: list[dict[str, Any]] = list(batch)
    if len(batch) < ps:
        return out, False

    for p in range(start_p + 1, max_p + 1):
        data = await sonar_client.issues_search(_search_params(component_key, p, extra))
        batch = list(data.get("issues") or [])
        out.extend(batch)
        await _sleep_between_pages()
        if len(batch) < ps:
            return out, False

    return out, len(batch) == ps


async def _fetch_pages_linear_capped(
    component_key: str,
    extra: dict[str, str],
    *,
    first_page: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """한 구간에 이슈가 과도하게 몰린 극단 케이스: 최대 `SONAR_ISSUES_MAX_RESULTS`건만."""
    ps = settings.sonar_issues_page_size
    max_p = _max_page_index(ps)

    if first_page is not None:
        data = first_page
    else:
        data = await sonar_client.issues_search(_search_params(component_key, 1, extra))

    batch = list(data.get("issues") or [])
    out: list[dict[str, Any]] = list(batch)
    if len(batch) < ps:
        return out

    for p in range(2, max_p + 1):
        data = await sonar_client.issues_search(_search_params(component_key, p, extra))
        batch = list(data.get("issues") or [])
        out.extend(batch)
        await _sleep_between_pages()
        if len(batch) < ps or len(out) >= SONAR_ISSUES_MAX_RESULTS:
            break
    return out[:SONAR_ISSUES_MAX_RESULTS]


async def _fetch_severity_date_shard(
    component_key: str,
    sonar_severity: str,
    t0: datetime,
    t1: datetime,
) -> list[dict[str, Any]]:
    """[t0, t1) 반열린 구간에서 단일 severity 수집. total > 10k 이면 이진 분할."""
    end_cap = _utc_tomorrow_start()
    t1 = min(t1, end_cap)
    if t1 <= t0:
        return []

    extra = {
        "severities": sonar_severity,
        "createdAfter": _iso_date_utc(t0),
        "createdBefore": _iso_date_utc(t1),
    }
    first = await sonar_client.issues_search(_search_params(component_key, 1, extra))
    total_n = _paging_total(first)

    if total_n is not None and total_n == 0:
        return []
    if total_n is not None and total_n <= SONAR_ISSUES_MAX_RESULTS:
        rows, _hit = await _fetch_pages_linear(component_key, extra, first_page=first)
        return rows

    if (t1 - t0) <= timedelta(days=1):
        logger.warning(
            "Sonar severity=%s created %s..%s has >%s issues; capping at %s.",
            sonar_severity,
            _iso_date_utc(t0),
            _iso_date_utc(t1),
            SONAR_ISSUES_MAX_RESULTS,
            SONAR_ISSUES_MAX_RESULTS,
        )
        return await _fetch_pages_linear_capped(component_key, extra, first_page=first)

    mid = t0 + (t1 - t0) / 2
    if mid <= t0:
        mid = t0 + timedelta(seconds=1)
    left = await _fetch_severity_date_shard(component_key, sonar_severity, t0, mid)
    right = await _fetch_severity_date_shard(component_key, sonar_severity, mid, t1)
    return _dedupe_by_key(left + right)


async def _fetch_one_sonar_severity(component_key: str, sonar_severity: str) -> list[dict[str, Any]]:
    extra = {"severities": sonar_severity}
    try:
        first = await sonar_client.issues_search(_search_params(component_key, 1, extra))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.info(
                "issues/search 400 for severity=%s — falling back to date-sharded fetch.",
                sonar_severity,
            )
            return await _fetch_severity_date_shard(
                component_key, sonar_severity, _RANGE_START, _utc_tomorrow_start()
            )
        raise

    total_n = _paging_total(first)
    if total_n is not None and total_n > SONAR_ISSUES_MAX_RESULTS:
        return await _fetch_severity_date_shard(
            component_key, sonar_severity, _RANGE_START, _utc_tomorrow_start()
        )

    ps = settings.sonar_issues_page_size
    batch = list(first.get("issues") or [])
    if len(batch) < ps:
        return batch

    if total_n is not None and total_n <= SONAR_ISSUES_MAX_RESULTS:
        linear, _hit = await _fetch_pages_linear(component_key, extra, first_page=first)
        return linear

    linear, hit_cap = await _fetch_pages_linear(component_key, extra, first_page=first)
    if hit_cap:
        logger.info(
            "severity=%s total unknown but hit %s-issue window — date-sharded fetch.",
            sonar_severity,
            SONAR_ISSUES_MAX_RESULTS,
        )
        return await _fetch_severity_date_shard(
            component_key, sonar_severity, _RANGE_START, _utc_tomorrow_start()
        )
    return linear


async def _fetch_by_severity_split(
    component_key: str,
    allowed: tuple[str, ...],
) -> list[dict[str, Any]]:
    acc: list[dict[str, Any]] = []
    for sv in allowed:
        chunk = await _fetch_one_sonar_severity(component_key, sv)
        acc.extend(chunk)
        await _sleep_between_pages()
    return _dedupe_by_key(acc)


async def _fetch_linear_full(
    component_key: str,
    extra: dict[str, str],
    allowed: tuple[str, ...],
) -> list[dict[str, Any]]:
    """프로브에서 total ≤ 10k 가 확인된 뒤, 설정 `ps`로 단일 필터 전량 페이징."""
    rows, hit_cap = await _fetch_pages_linear(component_key, extra, first_page=None)
    if hit_cap:
        logger.info(
            "Linear paging hit Sonar window after probe — severity-split.",
        )
        return await _fetch_by_severity_split(component_key, allowed)
    return rows


async def _fetch_unknown_total(
    component_key: str,
    extra: dict[str, str],
    allowed: tuple[str, ...],
) -> list[dict[str, Any]]:
    """프로브에 paging.total 이 없을 때: 본 `ps`로 첫 페이지부터 기존 페이징·상한 감지."""
    ps = settings.sonar_issues_page_size
    max_p = _max_page_index(ps)

    try:
        first = await sonar_client.issues_search(_search_params(component_key, 1, extra))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.info(
                "issues/search page 1 returned 400 — using severity-split fetch.",
            )
            return await _fetch_by_severity_split(component_key, allowed)
        raise

    total_n = _paging_total(first)
    if total_n is not None and total_n > SONAR_ISSUES_MAX_RESULTS:
        logger.info(
            "Sonar total=%s > %s — using severity-split fetch.",
            total_n,
            SONAR_ISSUES_MAX_RESULTS,
        )
        return await _fetch_by_severity_split(component_key, allowed)

    issues = list(first.get("issues") or [])
    if len(issues) < ps:
        return issues

    if total_n is not None and total_n > 0 and total_n <= len(issues):
        return issues

    all_issues: list[dict[str, Any]] = list(issues)
    last_batch = issues
    p = 2
    while p <= max_p:
        try:
            data = await sonar_client.issues_search(_search_params(component_key, p, extra))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.info(
                    "issues/search page %s returned 400 — using severity-split fetch.",
                    p,
                )
                return await _fetch_by_severity_split(component_key, allowed)
            raise
        batch = list(data.get("issues") or [])
        all_issues.extend(batch)
        last_batch = batch
        await _sleep_between_pages()
        if len(batch) < ps:
            return all_issues
        p += 1

    if len(last_batch) == ps and (total_n is None or total_n > len(all_issues)):
        logger.info(
            "Hit Sonar page cap (max p=%s, ps=%s); possible remaining issues — severity-split.",
            max_p,
            ps,
        )
        return await _fetch_by_severity_split(component_key, allowed)

    return all_issues


async def fetch_all_issues(
    component_key: str,
    severity_floor: str = "INFO",
) -> list[dict[str, Any]]:
    """
    OPEN 이슈 전량. Sonar 10k 제약을 넘기 위해 필요 시 severity·날짜 분할을 사용한다.

    먼저 `ps=1` 프로브로 `paging.total`만 읽고(별도 카운트 API 없음), 10k 초과 시
    곧바로 분할 수집해 첫 대량 페이지를 불필요하게 가져오지 않는다.

    `severity_floor` (표준 BLOCKER…INFO): 해당 레벨 **이상**만 수집 (예: MEDIUM → B·H·M).
    """
    floor = parse_severity_floor(severity_floor)
    allowed = sonar_native_severities_for_standard_floor(floor)
    extra = _extra_for_allowed(allowed)
    try:
        probe = await sonar_client.issues_search(
            _search_params(component_key, 1, extra, page_size=PROBE_PAGE_SIZE)
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.info(
                "issues/search probe (ps=%s) returned 400 — severity-split.",
                PROBE_PAGE_SIZE,
            )
            return await _fetch_by_severity_split(component_key, allowed)
        raise

    total_n = _paging_total(probe)

    if total_n is not None and total_n == 0:
        return []

    if total_n is not None and total_n > SONAR_ISSUES_MAX_RESULTS:
        logger.info(
            "Sonar total=%s > %s — severity-split (after probe).",
            total_n,
            SONAR_ISSUES_MAX_RESULTS,
        )
        return await _fetch_by_severity_split(component_key, allowed)

    if total_n is not None and total_n <= SONAR_ISSUES_MAX_RESULTS:
        return await _fetch_linear_full(component_key, extra, allowed)

    return await _fetch_unknown_total(component_key, extra, allowed)


async def fetch_open_issues_for_floor(
    component_key: str,
    severity_floor: str = "MEDIUM",
) -> list[dict[str, Any]]:
    """
    OPEN 이슈 중 `severity_floor` 이상(Sonar 네이티브로 OR 필터)만 수집.
    기본 MEDIUM — 기존 BLOCKER/CRITICAL/MAJOR(B·H·M) 3회 수집과 동일.
    """
    floor = parse_severity_floor(severity_floor)
    allowed = sonar_native_severities_for_standard_floor(floor)
    return await _fetch_by_severity_split(component_key, allowed)


async def fetch_open_issues_blocker_high_medium(component_key: str) -> list[dict[str, Any]]:
    """호환용 — `fetch_open_issues_for_floor(component_key, \"MEDIUM\")` 와 동일."""
    return await fetch_open_issues_for_floor(component_key, "MEDIUM")
