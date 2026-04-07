"""표준 severity 해석 — 웹 severity.js 와 대시보드 집계 일치."""
from __future__ import annotations

import unittest

from app.core.severity import resolve_issue_severity_raw, severity_bucket_for_issue


class SeverityIssueResolutionTests(unittest.TestCase):
    def test_top_severity_wins_over_impacts(self) -> None:
        """최상위 severity 가 있으면 impacts 는 보지 않음 (web/src/severity.js)."""
        issue = {
            "severity": "BLOCKER",
            "impacts": [{"severity": "CRITICAL"}],
        }
        self.assertEqual(resolve_issue_severity_raw(issue), "BLOCKER")
        self.assertEqual(severity_bucket_for_issue(issue), "BLOCKER")

    def test_empty_top_uses_strongest_impact(self) -> None:
        """Sonar 10.2+ — severity 비어 있으면 impacts 중 최고 등급."""
        issue = {
            "impacts": [
                {"severity": "MAJOR"},
                {"severity": "CRITICAL"},
            ],
        }
        self.assertEqual(resolve_issue_severity_raw(issue), "CRITICAL")
        self.assertEqual(severity_bucket_for_issue(issue), "HIGH")

    def test_critical_maps_to_high(self) -> None:
        issue = {"severity": "CRITICAL"}
        self.assertEqual(severity_bucket_for_issue(issue), "HIGH")


if __name__ == "__main__":
    unittest.main()
