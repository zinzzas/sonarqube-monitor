"""Sonar 10k 제약·severity 분할 fetch 로직."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.services.sonarqube_issues_fetch import (
    _fetch_severity_date_shard,
    fetch_all_issues,
    fetch_open_issues_for_floor,
)


class SonarIssuesFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_total_over_10k_skips_unfiltered_paging(self) -> None:
        """total > 10k 이면 severity 분할만 사용(첫 페이지 미필터는 버림)."""
        calls: list[dict[str, str]] = []

        async def fake_search(params: object) -> dict:
            p = dict(params) if isinstance(params, dict) else {}
            calls.append(p)
            if "severities" not in p:
                self.assertEqual(p.get("ps"), "1", "프로브는 ps=1")
                return {
                    "issues": [{"key": "probe"}],
                    "paging": {"total": 15_000},
                }
            sv = p.get("severities", "")
            return {
                "issues": [{"key": f"{sv}-{i}", "severity": sv} for i in range(5)],
                "paging": {"total": 5},
            }

        with patch(
            "app.services.sonarqube_issues_fetch.sonar_client.issues_search",
            new=AsyncMock(side_effect=fake_search),
        ):
            out = await fetch_all_issues("org:proj")

        self.assertEqual(len(out), 5 * 5)  # 5 severities × 5 issues
        self.assertTrue(all("severities" in c for c in calls[1:]))
        self.assertNotIn("severities", calls[0])

    async def test_medium_floor_probe_has_severities(self) -> None:
        """INFO가 아닌 하한이면 프로브부터 severities 포함."""
        calls: list[dict[str, str]] = []

        async def fake_search(params: object) -> dict:
            p = dict(params) if isinstance(params, dict) else {}
            calls.append(p)
            if p.get("ps") == "1":
                self.assertEqual(
                    p.get("severities"),
                    "BLOCKER,CRITICAL,MAJOR",
                )
                return {"issues": [], "paging": {"total": 0}}
            return {"issues": [], "paging": {"total": 0}}

        with patch(
            "app.services.sonarqube_issues_fetch.sonar_client.issues_search",
            new=AsyncMock(side_effect=fake_search),
        ):
            out = await fetch_all_issues("org:proj", "MEDIUM")

        self.assertEqual(out, [])
        self.assertTrue(calls)

    async def test_fetch_open_floor_high_two_calls(self) -> None:
        calls: list[str] = []

        async def fake_search(params: object) -> dict:
            p = dict(params) if isinstance(params, dict) else {}
            calls.append(str(p.get("severities", "")))
            return {"issues": [], "paging": {"total": 0}}

        with patch(
            "app.services.sonarqube_issues_fetch.sonar_client.issues_search",
            new=AsyncMock(side_effect=fake_search),
        ):
            await fetch_open_issues_for_floor("k", "HIGH")

        self.assertEqual([c for c in calls if c], ["BLOCKER", "CRITICAL"])

    async def test_under_10k_linear_only(self) -> None:
        async def fake_search(params: object) -> dict:
            p = dict(params) if isinstance(params, dict) else {}
            page = int(p.get("p", "1"))
            ps = int(p.get("ps", "300"))
            if page == 1 and ps == 1:
                return {
                    "issues": [{"key": "probe"}],
                    "paging": {"total": 400},
                }
            if page == 1 and ps == 300:
                return {
                    "issues": [{"key": f"x{i}", "severity": "MINOR"} for i in range(ps)],
                    "paging": {"total": 400},
                }
            return {
                "issues": [{"key": f"y{i}", "severity": "MINOR"} for i in range(100)],
                "paging": {"total": 400},
            }

        with patch(
            "app.services.sonarqube_issues_fetch.sonar_client.issues_search",
            new=AsyncMock(side_effect=fake_search),
        ):
            out = await fetch_all_issues("org:small")

        self.assertEqual(len(out), 400)

    async def test_http_400_on_page_triggers_split(self) -> None:
        import httpx

        async def fake_search(params: object) -> dict:
            p = dict(params) if isinstance(params, dict) else {}
            if "severities" in p:
                return {"issues": [], "paging": {"total": 0}}
            page = int(p.get("p", "1"))
            ps = int(p.get("ps", "300"))
            if ps == 1:
                return {"issues": [{"key": "p0"}], "paging": {}}
            if page == 1 and ps == 300:
                return {
                    "issues": [{"key": f"a{i}"} for i in range(300)],
                    "paging": {},
                }
            req = httpx.Request("GET", "http://x")
            raise httpx.HTTPStatusError("400", request=req, response=httpx.Response(400, request=req))

        with patch(
            "app.services.sonarqube_issues_fetch.sonar_client.issues_search",
            new=AsyncMock(side_effect=fake_search),
        ):
            out = await fetch_all_issues("org:weird")

        self.assertEqual(out, [])

    async def test_date_shard_caps_created_before_to_tomorrow(self) -> None:
        """2038 등 고정 상한으로 mid가 미래가 되면 Sonar 400 — 상한은 UTC 내일 0시."""
        captured: list[dict[str, str]] = []

        def _tomorrow_start_utc(from_dt: datetime) -> datetime:
            """프로덕션 `_utc_tomorrow_start` 와 동일한 산출(테스트에서만 재사용)."""
            d = from_dt.date() + timedelta(days=1)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

        # 재현 가능한 테스트용 “현재” 한 점만 고정 — 내일·createdBefore 문자열은 전부 여기서 유도
        frozen_now = datetime(2026, 4, 7, 12, 0, 0, tzinfo=timezone.utc)
        expected_tomorrow = _tomorrow_start_utc(frozen_now)
        expected_created_before = (frozen_now.date() + timedelta(days=1)).isoformat()

        async def fake_search(params: object) -> dict:
            p = dict(params) if isinstance(params, dict) else {}
            captured.append(p)
            return {"issues": [], "paging": {"total": 0}}

        with patch(
            "app.services.sonarqube_issues_fetch._utc_tomorrow_start",
            return_value=expected_tomorrow,
        ):
            with patch(
                "app.services.sonarqube_issues_fetch.sonar_client.issues_search",
                new=AsyncMock(side_effect=fake_search),
            ):
                await _fetch_severity_date_shard(
                    "k",
                    "MINOR",
                    datetime(2000, 1, 1, tzinfo=timezone.utc),
                    datetime(2038, 1, 1, tzinfo=timezone.utc),
                )

        self.assertTrue(captured)
        self.assertEqual(captured[0].get("createdBefore"), expected_created_before)


if __name__ == "__main__":
    unittest.main()
