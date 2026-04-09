"""maps.<profile>.exclude — pathPrefixes 는 롤업 경로 선두만, 중간 디렉터리는 pathContains."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.module_extract import is_excluded_from_module_rollup

_SAMPLE = "2856-all:src/main/java/net/cj/shrbatch/dashboard/service/DashBoardSaleDataService.java"


class JavaTreeExcludePathTests(unittest.TestCase):
    def test_path_prefix_dashboard_only_matches_leading_segment(self) -> None:
        """pathPrefixes 'dashboard' 는 rest 가 dashboard/... 로 시작할 때만 True."""
        cfg = {
            "pathPrefixes": ["dashboard"],
            "pathContains": [],
            "pathSegmentAny": [],
            "firstSegments": [],
            "fileSuffixes": [],
        }
        with patch("app.core.module_extract.exclude_rules_for_profile", return_value=cfg):
            self.assertFalse(is_excluded_from_module_rollup(_SAMPLE, "api-server"))

    def test_path_contains_slash_dashboard_matches_middle_segment(self) -> None:
        """중간 세그먼트 .../dashboard/... 는 pathContains 로만 안정적으로 제외."""
        cfg = {
            "pathPrefixes": [],
            "pathContains": ["/dashboard/"],
            "pathSegmentAny": [],
            "firstSegments": [],
            "fileSuffixes": [],
        }
        with patch("app.core.module_extract.exclude_rules_for_profile", return_value=cfg):
            self.assertTrue(is_excluded_from_module_rollup(_SAMPLE, "api-server"))

    def test_repo_config_excludes_shrbatch_dashboard_sample(self) -> None:
        """실제 module_segment_labels.json 의 java_tree.exclude 반영 시 제외."""
        self.assertTrue(is_excluded_from_module_rollup(_SAMPLE, "api-server"))


if __name__ == "__main__":
    unittest.main()
