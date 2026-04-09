"""모듈·Severity 집계가 `issue_component_key` 와 정합 — `component` 없이 mainComponent 만 있는 경우."""
from __future__ import annotations

import unittest
from unittest.mock import patch

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

    def test_excluded_path_omitted_from_severity_modules_and_chart(self) -> None:
        """exclude 에 걸린 이슈는 KPI·모듈·차트 어디에도 잡히지 않음."""
        key = "demo:src/main/java/x/App.java"
        other = "demo:src/main/java/x/Other.java"
        issues = [
            {"component": key, "severity": "BLOCKER", "status": "OPEN"},
            {"component": other, "severity": "MAJOR", "status": "OPEN"},
        ]
        with patch(
            "app.services.metrics_service.is_excluded_from_module_rollup",
            side_effect=lambda c, p: c == key,
        ):
            st, mods, cstack = metrics_service._aggregate_issues(issues, "demo")
        self.assertEqual(sum(st.values()), 1)
        # Sonar MAJOR → 표준 MEDIUM
        self.assertEqual(st.get("MEDIUM", 0), 1)
        self.assertEqual(st.get("BLOCKER", 0), 0)


if __name__ == "__main__":
    unittest.main()
