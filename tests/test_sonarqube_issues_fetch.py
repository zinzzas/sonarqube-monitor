"""Sonar 10k 제약·severity 분할 fetch 로직."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.services.sonarqube_issues_fetch import fetch_all_issues


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


if __name__ == "__main__":
    unittest.main()
