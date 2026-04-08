"""이슈 스냅샷 저장소 — TTL·severityFloor·원자적 기록."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import issue_snapshot_store


class IssueSnapshotStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_save_load_roundtrip_fresh(self) -> None:
        with patch.object(issue_snapshot_store.settings, "issue_snapshot_dir", self.root):
            pid = "proj-a"
            issues = [{"key": "k1", "component": "c"}]
            issue_snapshot_store.save_issues(
                pid, "full", issues, "comp:key", severity_floor="INFO"
            )
            loaded = issue_snapshot_store.load_issues_if_fresh(
                pid,
                "full",
                ttl_seconds=60.0,
                now=time.time(),
                expected_severity_floor="INFO",
            )
            self.assertEqual(loaded, issues)

    def test_load_none_when_expired(self) -> None:
        with patch.object(issue_snapshot_store.settings, "issue_snapshot_dir", self.root):
            pid = "proj-b"
            issue_snapshot_store.save_issues(
                pid, "full", [{"key": "x"}], "ck", severity_floor="INFO"
            )
            loaded = issue_snapshot_store.load_issues_if_fresh(
                pid,
                "full",
                ttl_seconds=1.0,
                now=time.time() + 10.0,
                expected_severity_floor="INFO",
            )
            self.assertIsNone(loaded)

    def test_load_none_when_severity_floor_mismatch(self) -> None:
        with patch.object(issue_snapshot_store.settings, "issue_snapshot_dir", self.root):
            pid = "proj-floor"
            issue_snapshot_store.save_issues(
                pid, "full", [{"key": "x"}], "ck", severity_floor="INFO"
            )
            loaded = issue_snapshot_store.load_issues_if_fresh(
                pid,
                "full",
                ttl_seconds=3600.0,
                now=time.time(),
                expected_severity_floor="MEDIUM",
            )
            self.assertIsNone(loaded)

    def test_legacy_manifest_without_severity_floor_is_stale(self) -> None:
        """구형 manifest(키 없음)은 한 번 무시되어 재수집으로 이행."""
        with patch.object(issue_snapshot_store.settings, "issue_snapshot_dir", self.root):
            pid = "proj-legacy"
            d = issue_snapshot_store.project_dir(pid)
            d.mkdir(parents=True)
            manifest = {
                "full": {
                    "savedAt": time.time(),
                    "componentKey": "ck",
                    "issueCount": 0,
                },
            }
            (d / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            (d / "issues_full.json").write_text("[]", encoding="utf-8")
            loaded = issue_snapshot_store.load_issues_if_fresh(
                pid,
                "full",
                ttl_seconds=3600.0,
                now=time.time(),
                expected_severity_floor="INFO",
            )
            self.assertIsNone(loaded)

    def test_clear_all_removes_tree(self) -> None:
        with patch.object(issue_snapshot_store.settings, "issue_snapshot_dir", self.root):
            issue_snapshot_store.save_issues("p1", "bhm", [], "ck", severity_floor="MEDIUM")
            self.assertTrue(any(self.root.iterdir()))
            issue_snapshot_store.clear_all_snapshots()
            self.assertFalse(any(self.root.iterdir()))
