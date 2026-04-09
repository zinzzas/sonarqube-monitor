"""스택 축: 프로필별 strip·앵커. component_projects/stack 보조 및 projectProfiles 우선."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.module_extract import chart_stack_bucket, profile_id_for_project
from app.core.module_path_tree import chart_rest_after_anchor, chart_stack_bucket as chart_stack_bucket_raw


class ChartStackAnchorTests(unittest.TestCase):
    _samples = {
        "auth": "p:src/main/java/com/hhi/hihr/com/auth/controller/ComAuthController.java",
        "atm_biz": "p:src/main/java/com/hhi/hihr/atm/bizcom/service/AttendanceComService.java",
        "atm_ctrl": "p:src/main/java/com/hhi/hihr/atm/annualmonthlyleaveplanaccrual/controller/AnnualLeaveAccrualApplicationController.java",
    }

    def test_java_tree_api_server_com_atm_buckets(self) -> None:
        """java_tree + com/hhi/hihr/ 앵커 — hihr 직후 com / atm."""
        for key, comp in self._samples.items():
            b = chart_stack_bucket(comp, "api-server")
            if key == "auth":
                self.assertEqual(b, "com", (key, comp))
            else:
                self.assertEqual(b, "atm", (key, comp))

    def test_unmapped_project_id_uses_vue_default_first_segment_main(self) -> None:
        """목록에 없는 id → vue 기본 → Java 경로는 첫 세그먼트 main."""
        comp = self._samples["auth"]
        self.assertEqual(chart_stack_bucket(comp, "some-other-sonar-key"), "main")

    def test_stack_java_row_uses_java_tree_without_project_profiles_entry(self) -> None:
        """component_projects 에 stack:java 만 있고 projectProfiles 에 id 가 없어도 java_tree 적용."""
        comp = "adhoc-java:src/main/java/com/hhi/hihr/com/auth/controller/ComAuthController.java"
        fake = [
            {
                "id": "adhoc-java",
                "label": "Adhoc",
                "componentKey": "sonar-key",
                "stack": "java",
            }
        ]
        with patch("app.core.module_extract.load_component_projects", return_value=fake):
            self.assertEqual(profile_id_for_project("adhoc-java"), "java_tree")
            self.assertEqual(chart_stack_bucket(comp, "adhoc-java"), "com")

    def test_project_profiles_overrides_stack_field(self) -> None:
        """projectProfiles 명시가 stack 보조보다 우선."""
        self.assertEqual(profile_id_for_project("h1"), "vue_src_tree")

    def test_leading_slash_in_anchor_matches(self) -> None:
        prof = {
            "strategy": "path_tree",
            "stripPrefixes": [
                "src/main/java/net/cj/",
                "src/main/java/net/cj",
                "src/main/java/",
                "src/main/java",
            ],
            "anchorAfter": "",
            "chartStackAnchorAfter": "/com/hhi/hihr/",
            "maxDepth": 7,
        }
        comp = self._samples["auth"]
        self.assertEqual(chart_stack_bucket_raw(comp, prof), "com")
        self.assertIn("com/auth", chart_rest_after_anchor(comp, prof))


if __name__ == "__main__":
    unittest.main()
