"""HIGH RISK 팀 매칭: 경로 세그먼트 추출·fallback 동작."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.core.severity import severity_bucket_for_issue
from app.core.team_high_risk import aggregate_high_risk_by_team, team_id_for_path_segments


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


class TeamIdPathSegmentsParityTests(unittest.TestCase):
    """대시보드 집계와 이슈 목록 팀 필터: 빈 세그먼트는 선행 규칙 매칭 없음 → fallback(shared)만."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._cfg = Path(self._tmp.name) / "module_segment_labels.json"
        tm = {
            "precedence": [
                {
                    "teamId": "team_d",
                    "label": "공통",
                    "when": {"modules": ["common"], "match": "any"},
                },
            ],
            "fallback": {"teamId": "shared", "label": "ETC"},
        }
        self._cfg.write_text(
            json.dumps({"version": 1, "teamMapping": tm, "maps": {}}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        patcher = patch(
            "app.config.load_module_segment_labels._CONFIG_PATH",
            self._cfg,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_empty_segments_map_to_fallback_not_precedence_team(self) -> None:
        """세그먼트 없음 → team_d(공통) 조건은 평가되지 않고 shared(ETC). 이슈 목록 팀 필터와 정합."""
        tid = team_id_for_path_segments([], None)
        self.assertEqual(tid, "shared")

    def test_common_segment_maps_to_team_d(self) -> None:
        tid = team_id_for_path_segments(["portal", "common"], None)
        self.assertEqual(tid, "team_d")


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

    def test_path_tree_anchor_missing_no_strip_fallback_for_team_match(self) -> None:
        """anchorAfter(/fims/)가 있는데 경로에 앵커가 없으면 strip 경로로 팀 매칭하지 않음 → fallback."""
        comp = "proj:src/main/java/com/acme/portal/domain/Foo.java"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_tree_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "api-server",
                severity_key_fn=severity_bucket_for_issue,
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 0, counts)
        self.assertEqual(counts.get("shared", 0), 1, counts)

    def test_path_tree_anchor_missing_com_module_not_matched_from_package_segment(self) -> None:
        """패키지 com/.../com 과 팀 모듈 com 이 strip 폴백으로 섞이지 않음(앵커 필수 프로필)."""
        tm = {
            "precedence": [
                {
                    "teamId": "team_a",
                    "label": "A",
                    "when": {"modules": ["com"], "match": "any"},
                }
            ],
            "fallback": {"teamId": "shared", "label": "ETC"},
        }
        comp = "proj:src/main/java/com/hhi/hihr/com/Foo.java"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_tree_profile()):
            with patch("app.core.team_high_risk.team_mapping_config", return_value=tm):
                counts = aggregate_high_risk_by_team(
                    issues,
                    "api-server",
                    severity_key_fn=severity_bucket_for_issue,
                    is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
                )
        self.assertEqual(counts.get("team_a", 0), 0, counts)
        self.assertEqual(counts.get("shared", 0), 1, counts)

    def test_path_tree_with_fims_still_prefers_anchor_segments(self) -> None:
        comp = "proj:src/main/java/com/x/fims/portal/domain/Foo.java"
        issues = [{"component": comp, "severity": "HIGH"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_tree_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "api-server",
                severity_key_fn=severity_bucket_for_issue,
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)

    def test_aggregate_main_component_key_equivalent_to_component(self) -> None:
        """이슈 목록·스냅샷 teamId 와 동일: `component` 없이 `mainComponent.key` 만 있어도 동일 버킷."""
        comp = "proj:src/main/java/com/x/fims/portal/domain/Foo.java"
        with patch("app.core.team_high_risk.profile_for_project", return_value=_java_tree_profile()):
            c_component = aggregate_high_risk_by_team(
                [{"component": comp, "severity": "HIGH"}],
                "api-server",
                severity_key_fn=severity_bucket_for_issue,
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
            c_main = aggregate_high_risk_by_team(
                [{"mainComponent": {"key": comp}, "severity": "HIGH"}],
                "api-server",
                severity_key_fn=severity_bucket_for_issue,
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(c_component, c_main)

    def test_vue_path_tree_domain_under_api(self) -> None:
        comp = "h1:src/api/domain/foo/Bar.vue"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_vue_tree_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "h1",
                severity_key_fn=severity_bucket_for_issue,
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)

    def test_split_after_segment_index_oob_still_matches_any(self) -> None:
        """split_after: extract_module OOB 이후에도 `after`(/fims/) 이후 세그먼트(domain)로 any 매칭."""
        comp = "legacy:src/x/fims/portal/domain/Foo.java"
        issues = [{"component": comp, "severity": "BLOCKER"}]
        with patch("app.core.team_high_risk.profile_for_project", return_value=_split_after_oob_profile()):
            counts = aggregate_high_risk_by_team(
                issues,
                "legacy",
                severity_key_fn=severity_bucket_for_issue,
                is_high_risk_fn=lambda s: s in ("BLOCKER", "HIGH"),
            )
        self.assertEqual(counts.get("team_a", 0), 1, counts)


if __name__ == "__main__":
    unittest.main()
