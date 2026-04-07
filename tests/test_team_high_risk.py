"""HIGH RISK 팀 매칭: 경로 세그먼트 추출·fallback 동작."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.core.team_high_risk import aggregate_high_risk_by_team


def _java_tree_profile() -> dict:
    return {
        "strategy": "path_tree",
        "stripPrefixes": ["src/main/java/", "src/main/java"],
        "anchorAfter": "/fims/",
        "maxDepth": 2,
    }


def _vue_tree_profile() -> dict:
    return {
        "strategy": "path_tree",
        "stripPrefixes": ["src/"],
        "anchorAfter": "",
        "maxDepth": 7,
    }


def _split_after_oob_profile() -> dict:
    """segment_index 가 경로 길이보다 크면 extract_module 은 unknown — 팀 매칭은 앵커 이후 세그먼트로."""
    return {
        "strategy": "split_after",
        "after": "/fims/",
        "segment_index": 99,
    }


class TeamHighRiskSegmentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._cfg = Path(self._tmp.name) / "module_segment_labels.json"
        tm = {
            "precedence": [
                {
                    "teamId": "team_a",
                    "label": "A",
                    "when": {"modules": ["domain"], "match": "any"},
                }
            ],
            "fallback": {"teamId": "shared", "label": "ETC"},
        }
        self._cfg.write_text(
            json.dumps({"version": 1, "teamMapping": tm, "maps": {}}, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        patcher = patch(
            "app.config.load_module_segment_labels._CONFIG_PATH",
            self._cfg,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_path_tree_anchor_missing_uses_strip_fallback_not_all_etc(self) -> None:
        """경로에 /fims/ 가 없어도 strip 이후 세그먼트로 팀 매칭."""
        comp = "proj:src/main/java/com/acme/portal/domain/Foo.java"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_tree_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "api-server",
                severity_key_fn=lambda s: str(s or ""),
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)
        self.assertEqual(counts.get("shared", 0), 0, counts)

    def test_path_tree_with_fims_still_prefers_anchor_segments(self) -> None:
        comp = "proj:src/main/java/com/x/fims/portal/domain/Foo.java"
        issues = [{"component": comp, "severity": "HIGH"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_tree_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "api-server",
                severity_key_fn=lambda s: str(s or ""),
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)

    def test_vue_path_tree_domain_under_api(self) -> None:
        comp = "h1:src/api/domain/foo/Bar.vue"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_vue_tree_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "h1",
                severity_key_fn=lambda s: str(s or ""),
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)

    def test_split_after_segment_index_oob_still_matches_any(self) -> None:
        comp = "legacy:src/x/fims/portal/domain/Foo.java"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_split_after_oob_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "legacy",
                severity_key_fn=lambda s: str(s or ""),
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)


if __name__ == "__main__":
    unittest.main()
