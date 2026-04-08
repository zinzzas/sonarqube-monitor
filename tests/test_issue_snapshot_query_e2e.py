"""스냅샷 파일 + 실제 try_issue_search_from_snapshot (모킹 최소)."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services import issue_snapshot_store
from app.services.issue_snapshot_query import try_issue_search_from_snapshot


class IssueSnapshotQueryE2ETests(unittest.TestCase):
    def test_disk_snapshot_serves_search(self) -> None:
        issues = [
            {
                "key": "e2e-1",
                "status": "OPEN",
                "severity": "BLOCKER",
                "component": "myck:src/X.java",
                "creationDate": "2025-01-01T12:00:00+0000",
            },
        ]
        rows = [{"id": "proj-e2e", "label": "E2E", "componentKey": "myck"}]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(settings, "issue_snapshot_dir", root):
                issue_snapshot_store.save_issues(
                    "proj-e2e", "full", issues, "myck", severity_floor="INFO"
                )
                pairs = [
                    ("componentKeys", "myck"),
                    ("p", "1"),
                    ("ps", "50"),
                    ("statuses", "OPEN"),
                    ("s", "SEVERITY"),
                    ("asc", "false"),
                ]
                with patch(
                    "app.config.load_projects.load_component_projects",
                    return_value=rows,
                ):
                    out = try_issue_search_from_snapshot(pairs, now=time.time())
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["total"], 1)
        self.assertEqual(out["issues"][0]["key"], "e2e-1")
