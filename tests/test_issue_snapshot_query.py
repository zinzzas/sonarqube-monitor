"""스냅샷 기반 `issues/search` 로컬 쿼리."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from app.services.issue_snapshot_query import (
    strip_internal_query_params,
    try_issue_search_from_snapshot,
)


def _stub_team_id(issue, _pid):
    return "team_a" if issue.get("key") == "k1" else "team_b"


class IssueSnapshotQueryTests(unittest.TestCase):
    def test_strip_source_param(self) -> None:
        pairs = [("componentKeys", "a"), ("source", "live"), ("p", "1")]
        self.assertEqual(
            strip_internal_query_params(pairs),
            [("componentKeys", "a"), ("p", "1")],
        )

    def test_strip_teamid_param(self) -> None:
        pairs = [("componentKeys", "a"), ("teamId", "x"), ("p", "1")]
        self.assertEqual(
            strip_internal_query_params(pairs),
            [("componentKeys", "a"), ("p", "1")],
        )

    def test_none_when_sort_missing(self) -> None:
        pairs = [
            ("componentKeys", "ck"),
            ("p", "1"),
            ("ps", "50"),
            ("statuses", "OPEN"),
        ]
        self.assertIsNone(try_issue_search_from_snapshot(pairs))

    def test_none_when_multi_component_keys(self) -> None:
        pairs = [
            ("componentKeys", "a,b"),
            ("p", "1"),
            ("ps", "50"),
            ("statuses", "OPEN"),
            ("s", "SEVERITY"),
            ("asc", "false"),
        ]
        self.assertIsNone(try_issue_search_from_snapshot(pairs))

    def test_none_unknown_sort_field(self) -> None:
        pairs = [
            ("componentKeys", "ck"),
            ("p", "1"),
            ("ps", "50"),
            ("statuses", "OPEN"),
            ("s", "FILE_LINE"),
            ("asc", "false"),
        ]
        self.assertIsNone(try_issue_search_from_snapshot(pairs))

    def test_none_source_live(self) -> None:
        pairs = [
            ("componentKeys", "ck"),
            ("source", "live"),
            ("p", "1"),
            ("ps", "50"),
            ("statuses", "OPEN"),
            ("s", "SEVERITY"),
            ("asc", "false"),
        ]
        self.assertIsNone(try_issue_search_from_snapshot(pairs))

    def test_filter_severity_status_page(self) -> None:
        issues = [
            {
                "key": "k1",
                "status": "OPEN",
                "severity": "BLOCKER",
                "component": "ck:src/A.java",
                "creationDate": "2024-01-02T00:00:00+0000",
            },
            {
                "key": "k2",
                "status": "OPEN",
                "severity": "CRITICAL",
                "component": "ck:src/B.java",
                "creationDate": "2024-01-01T00:00:00+0000",
            },
            {
                "key": "k3",
                "status": "CLOSED",
                "severity": "BLOCKER",
                "component": "ck:src/C.java",
                "creationDate": "2024-01-03T00:00:00+0000",
            },
        ]
        row = {"id": "proj1", "componentKey": "ck", "label": "X"}
        pairs = [
            ("componentKeys", "ck"),
            ("p", "1"),
            ("ps", "10"),
            ("statuses", "OPEN"),
            ("severities", "BLOCKER,CRITICAL"),
            ("s", "CREATION_DATE"),
            ("asc", "false"),
        ]
        with patch(
            "app.services.issue_snapshot_query.project_row_by_component_key",
            return_value=row,
        ):
            with patch(
                "app.services.issue_snapshot_query.issue_snapshot_store.load_issues_if_fresh",
                return_value=issues,
            ):
                out = try_issue_search_from_snapshot(pairs, now=time.time())
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["total"], 2)
        self.assertEqual(len(out["issues"]), 2)
        keys = [x["key"] for x in out["issues"]]
        self.assertEqual(keys[0], "k1")

    def test_team_id_filter(self) -> None:
        issues = [
            {"key": "k1", "status": "OPEN", "severity": "BLOCKER", "component": "ck:a"},
            {"key": "k2", "status": "OPEN", "severity": "BLOCKER", "component": "ck:b"},
        ]
        row = {"id": "proj1", "componentKey": "ck"}
        pairs = [
            ("componentKeys", "ck"),
            ("teamId", "team_a"),
            ("p", "1"),
            ("ps", "50"),
            ("statuses", "OPEN"),
            ("s", "SEVERITY"),
            ("asc", "false"),
        ]
        with patch(
            "app.services.issue_snapshot_query.project_row_by_component_key",
            return_value=row,
        ):
            with patch(
                "app.services.issue_snapshot_query.issue_snapshot_store.load_issues_if_fresh",
                return_value=issues,
            ):
                with patch(
                    "app.services.issue_snapshot_query.team_id_for_issue_row",
                    side_effect=_stub_team_id,
                ):
                    out = try_issue_search_from_snapshot(pairs, now=time.time())
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["total"], 1)
        self.assertEqual(out["issues"][0]["key"], "k1")

    def test_severity_sort_desc(self) -> None:
        issues = [
            {"key": "low", "status": "OPEN", "severity": "MINOR", "component": "c"},
            {"key": "hi", "status": "OPEN", "severity": "BLOCKER", "component": "c"},
        ]
        row = {"id": "p", "componentKey": "ck"}
        pairs = [
            ("componentKeys", "ck"),
            ("p", "1"),
            ("ps", "50"),
            ("statuses", "OPEN"),
            ("s", "SEVERITY"),
            ("asc", "false"),
        ]
        with patch(
            "app.services.issue_snapshot_query.project_row_by_component_key",
            return_value=row,
        ):
            with patch(
                "app.services.issue_snapshot_query.issue_snapshot_store.load_issues_if_fresh",
                return_value=issues,
            ):
                out = try_issue_search_from_snapshot(pairs, now=time.time())
        assert out is not None
        self.assertEqual([i["key"] for i in out["issues"]], ["hi", "low"])
