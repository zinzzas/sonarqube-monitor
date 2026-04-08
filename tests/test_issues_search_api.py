"""`GET /api/issues/search` — 스냅샷 경로 시 Sonar 프록시 미호출."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class IssuesSearchApiTests(unittest.TestCase):
    def test_snapshot_branch_skips_sonar_proxy(self) -> None:
        from main import app

        client = TestClient(app)
        payload = {
            "total": 0,
            "paging": {"pageIndex": 1, "pageSize": 50, "total": 0},
            "issues": [],
        }
        with patch(
            "app.api.issues.try_issue_search_from_snapshot",
            return_value=payload,
        ):
            with patch(
                "app.api.issues.proxy_issues_search",
                new_callable=AsyncMock,
            ) as m_proxy:
                r = client.get(
                    "/api/issues/search"
                    "?componentKeys=dummy"
                    "&p=1&ps=50&statuses=OPEN"
                    "&s=SEVERITY&asc=false",
                )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body.get("total"), 0)
        self.assertEqual(body.get("issues"), [])
        m_proxy.assert_not_called()

    def test_proxy_called_when_snapshot_returns_none(self) -> None:
        from main import app

        client = TestClient(app)
        sonar_like = {
            "total": 1,
            "paging": {"pageIndex": 1, "pageSize": 50, "total": 1},
            "issues": [{"key": "k", "status": "OPEN", "severity": "BLOCKER", "component": "x"}],
        }
        with patch(
            "app.api.issues.try_issue_search_from_snapshot",
            return_value=None,
        ):
            with patch(
                "app.api.issues.proxy_issues_search",
                new_callable=AsyncMock,
                return_value=sonar_like,
            ) as m_proxy:
                r = client.get(
                    "/api/issues/search"
                    "?componentKeys=dummy"
                    "&p=1&ps=50&statuses=OPEN"
                    "&s=SEVERITY&asc=false",
                )
        self.assertEqual(r.status_code, 200, r.text)
        m_proxy.assert_called_once()
        args = m_proxy.call_args[0][0]
        keys = [k for k, _ in args]
        self.assertNotIn("source", keys)
        self.assertNotIn("teamId", keys)

    def test_proxy_strips_teamid_for_upstream(self) -> None:
        from main import app

        client = TestClient(app)
        sonar_like = {
            "total": 0,
            "paging": {"pageIndex": 1, "pageSize": 50, "total": 0},
            "issues": [],
        }
        with patch(
            "app.api.issues.try_issue_search_from_snapshot",
            return_value=None,
        ):
            with patch(
                "app.api.issues.proxy_issues_search",
                new_callable=AsyncMock,
                return_value=sonar_like,
            ) as m_proxy:
                client.get(
                    "/api/issues/search"
                    "?componentKeys=dummy"
                    "&p=1&ps=50&statuses=OPEN"
                    "&s=SEVERITY&asc=false"
                    "&teamId=team_a",
                )
        args = m_proxy.call_args[0][0]
        keys = [k for k, _ in args]
        self.assertNotIn("teamId", keys)
