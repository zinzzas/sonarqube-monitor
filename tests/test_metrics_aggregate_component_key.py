"""모듈·Severity 집계가 `issue_component_key` 와 정합 — `component` 없이 mainComponent 만 있는 경우."""
from __future__ import annotations

import unittest

from app.services import metrics_service


class MetricsAggregateComponentKeyTests(unittest.TestCase):
    def test_main_component_only_matches_explicit_component_string(self) -> None:
        key = "demo:src/main/java/x/App.java"
        with_component = [{"component": key, "severity": "BLOCKER", "status": "OPEN"}]
        main_only = [{"mainComponent": {"key": key}, "severity": "BLOCKER", "status": "OPEN"}]
        a = metrics_service._aggregate_issues(with_component, "demo")
        b = metrics_service._aggregate_issues(main_only, "demo")
        self.assertEqual(a[0], b[0], "severityTotal 동일")
        self.assertEqual(a[1], b[1], "modules 동일")
        self.assertEqual(a[2], b[2], "chartStackModules 동일")


if __name__ == "__main__":
    unittest.main()
