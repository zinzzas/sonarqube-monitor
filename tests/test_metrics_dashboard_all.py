"""`/api/metrics/dashboard?projectId=all` — 전 프로젝트 B·H·M 병합."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class MetricsDashboardAllTests(unittest.TestCase):
    def test_all_returns_aggregate_mode_and_merges_rows(self) -> None:
        projects = [
            {"id": "p1", "label": "Alpha", "componentKey": "ck1"},
            {"id": "p2", "label": "Beta", "componentKey": "ck2"},
        ]
        labels = {"p1": "Alpha", "p2": "Beta"}

        with patch(
            "app.services.metrics_service.fetch_open_issues_for_floor",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "app.services.metrics_service.load_component_projects",
                return_value=projects,
            ):
                with patch(
                    "app.services.metrics_service.project_labels_map",
                    return_value=labels,
                ):
                    import app.services.metrics_service as metrics_service

                    metrics_service.invalidate_dashboard_cache()
                    from main import app

                    client = TestClient(app)
                    r = client.get("/api/metrics/dashboard?projectId=all")

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body.get("aggregateMode"), "all_bhm")
        self.assertEqual(body.get("projectId"), "all")
        self.assertEqual(len(body.get("byProject", [])), 2)
        self.assertEqual(body["summary"]["totalIssues"], 0)
        self.assertEqual(body["summary"]["highRisk"], 0)
        self.assertEqual(body.get("globalModules"), {})
        self.assertEqual(body.get("globalChartStackModules"), {})

    def test_all_when_no_component_keys_still_returns_all_bhm_not_no_data(self) -> None:
        """componentKey 가 전부 비어 있어도 ALL 은 병합 모드(0건), no_data 가 아님."""
        rows = [
            {"id": "p1", "label": "Only", "componentKey": ""},
        ]
        with patch(
            "app.services.metrics_service.load_component_projects",
            return_value=rows,
        ):
            with patch(
                "app.services.metrics_service.project_labels_map",
                return_value={"p1": "Only"},
            ):
                import app.services.metrics_service as metrics_service

                metrics_service.invalidate_dashboard_cache()
                from main import app

                client = TestClient(app)
                r = client.get("/api/metrics/dashboard?projectId=all")

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body.get("aggregateMode"), "all_bhm")
        self.assertEqual(body["summary"]["totalIssues"], 0)
        self.assertEqual(body.get("errors"), [])

    def test_single_project_includes_project_full_mode(self) -> None:
        projects = [
            {"id": "only", "label": "Only", "componentKey": "ck"},
        ]
        with patch(
            "app.services.metrics_service.fetch_all_issues",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch(
                "app.services.metrics_service.projects_with_keys",
                return_value=projects,
            ):
                with patch(
                    "app.services.metrics_service.project_labels_map",
                    return_value={"only": "Only"},
                ):
                    import app.services.metrics_service as metrics_service

                    metrics_service.invalidate_dashboard_cache()
                    from main import app

                    client = TestClient(app)
                    r = client.get("/api/metrics/dashboard?projectId=only")

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("aggregateMode"), "project_full")

