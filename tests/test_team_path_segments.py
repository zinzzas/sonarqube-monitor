"""팀 매칭용 경로 세그먼트: path_tree 앵커 이후·split_after 앵커 일관성."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.team_high_risk import (
    aggregate_high_risk_by_team,
    path_segments_for_team_match,
    team_id_for_path_segments,
)
from app.core.severity import severity_bucket_for_issue


def _java_hhi_anchor_profile() -> dict:
    """strip 후 anchor /hhi/ 이후만 비즈니스 모듈 토큰 (Java 패키지 com 과 구분)."""
    return {
        "strategy": "path_tree",
        "stripPrefixes": ["src/main/java/", "src/main/java"],
        "anchorAfter": "/hhi/",
        "maxDepth": 8,
    }


def _java_fims_profile() -> dict:
    return {
        "strategy": "path_tree",
        "stripPrefixes": ["src/main/java/", "src/main/java"],
        "anchorAfter": "/fims/",
        "maxDepth": 2,
    }


def _vue_empty_anchor_profile() -> dict:
    return {
        "strategy": "path_tree",
        "stripPrefixes": ["src/"],
        "anchorAfter": "",
        "maxDepth": 7,
    }


def _split_after_default_profile() -> dict:
    return {
        "strategy": "split_after",
        "after": "/fims/",
        "segment_index": 1,
    }


def _split_after_oob_profile() -> dict:
    return {
        "strategy": "split_after",
        "after": "/fims/",
        "segment_index": 99,
    }


class PathSegmentsForTeamMatchTests(unittest.TestCase):
    """path_tree: rollup_path_after_anchor 이후 세그먼트만 팀 매칭에 사용."""

    def test_hhi_anchor_com_after_hhi_segments(self) -> None:
        comp = "p:src/main/java/com/hhi/com/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_hhi_anchor_profile()):
            segs = path_segments_for_team_match(comp, "x")
        self.assertEqual(segs, ["com"])

    def test_hhi_anchor_hiway_not_com(self) -> None:
        comp = "p:src/main/java/com/hhi/hiway/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_hhi_anchor_profile()):
            segs = path_segments_for_team_match(comp, "x")
        self.assertEqual(segs, ["hiway"])

    def test_leading_java_com_not_matched_when_only_post_hhi_used(self) -> None:
        """패키지 최상위 com 은 /hhi/ 앞이면 세그먼트에 포함되지 않음."""
        comp = "p:src/main/java/com/hhi/hiway/Bar.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_hhi_anchor_profile()):
            segs = path_segments_for_team_match(comp, "x")
        self.assertNotIn("com", segs)

    def test_com_module_match_any_true_only_when_com_after_hhi(self) -> None:
        mapping = {
            "precedence": [
                {"teamId": "team_com", "label": "C", "when": {"modules": ["com"], "match": "any"}},
            ],
            "fallback": {"teamId": "shared", "label": "ETC"},
        }
        comp_match = "p:src/main/java/com/hhi/com/Foo.java"
        comp_no = "p:src/main/java/com/hhi/hiway/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_hhi_anchor_profile()):
            self.assertEqual(
                team_id_for_path_segments(path_segments_for_team_match(comp_match, "x"), mapping),
                "team_com",
            )
            self.assertEqual(
                team_id_for_path_segments(path_segments_for_team_match(comp_no, "x"), mapping),
                "shared",
            )

    def test_fims_anchor_domain_segment(self) -> None:
        comp = "p:src/main/java/com/x/fims/portal/domain/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_fims_profile()):
            segs = path_segments_for_team_match(comp, "x")
        self.assertIn("domain", segs)

    def test_path_tree_anchor_missing_returns_empty(self) -> None:
        comp = "p:src/main/java/com/acme/foo/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_fims_profile()):
            segs = path_segments_for_team_match(comp, "x")
        self.assertEqual(segs, [])

    def test_vue_empty_anchor_uses_strip_fallback(self) -> None:
        comp = "h1:src/api/domain/x/Bar.vue"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_vue_empty_anchor_profile()):
            segs = path_segments_for_team_match(comp, "h1")
        self.assertIn("domain", segs)


class SplitAfterTeamSegmentsTests(unittest.TestCase):
    """split_after: 경로에 after 앵커가 없으면 strip_only 로 domain 등 오매칭하지 않음."""

    def test_anchor_missing_returns_empty_not_strip(self) -> None:
        comp = "p:src/main/java/com/hi/portal/domain/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_split_after_default_profile()):
            segs = path_segments_for_team_match(comp, "legacy")
        self.assertEqual(segs, [])

    def test_oob_extract_uses_after_segments_for_domain(self) -> None:
        """segment_index OOB 시에도 after 이후 전체 세그먼트로 domain 매칭."""
        comp = "legacy:src/x/fims/portal/domain/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_split_after_oob_profile()):
            segs = path_segments_for_team_match(comp, "legacy")
        self.assertIn("domain", segs)


class AggregateHhiAnchorTests(unittest.TestCase):
    """aggregate_high_risk_by_team — com 모듈 토큰은 /hhi/ 이후 com 일 때만."""

    def setUp(self) -> None:
        self._tm = {
            "precedence": [
                {"teamId": "team_com", "label": "C", "when": {"modules": ["com"], "match": "any"}},
            ],
            "fallback": {"teamId": "shared", "label": "ETC"},
        }

    def test_com_under_hhi_counts_team_com(self) -> None:
        comp = "p:src/main/java/com/hhi/com/Foo.java"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_hhi_anchor_profile()):
            with patch("app.core.team_high_risk.team_mapping_config", return_value=self._tm):
                counts = aggregate_high_risk_by_team(
                    issues,
                    "api",
                    severity_key_fn=severity_bucket_for_issue,
                    is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
                )
        self.assertEqual(counts.get("team_com", 0), 1, counts)
        self.assertEqual(counts.get("shared", 0), 0, counts)

    def test_hiway_under_hhi_not_team_com(self) -> None:
        comp = "p:src/main/java/com/hhi/hiway/Foo.java"
        issues = [{"component": comp, "severity": "HIGH"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_hhi_anchor_profile()):
            with patch("app.core.team_high_risk.team_mapping_config", return_value=self._tm):
                counts = aggregate_high_risk_by_team(
                    issues,
                    "api",
                    severity_key_fn=severity_bucket_for_issue,
                    is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
                )
        self.assertEqual(counts.get("team_com", 0), 0, counts)
        self.assertEqual(counts.get("shared", 0), 1, counts)


if __name__ == "__main__":
    unittest.main()
