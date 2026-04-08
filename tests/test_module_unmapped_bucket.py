"""내부 'unknown' 모듈 토큰 → module_grouping 의 표시용 축 이름(chartStackUnmappedBucket)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core import module_extract


class ChartStackUnmappedBucketTests(unittest.TestCase):
    def test_defaults_label(self) -> None:
        cfg = {
            "defaults": {"chartStackUnmappedBucket": "unmapped-display"},
            "profiles": {"vue_src_tree": {"strategy": "path_tree"}},
            "defaultProfile": "vue_src_tree",
            "projectProfiles": {},
        }
        with patch("app.core.module_extract.load_module_grouping", return_value=cfg):
            self.assertEqual(
                module_extract.chart_stack_unmapped_bucket("any-project"),
                "unmapped-display",
            )

    def test_profile_overrides_defaults(self) -> None:
        cfg = {
            "defaults": {"chartStackUnmappedBucket": "from-default"},
            "profiles": {
                "java_tree": {
                    "strategy": "path_tree",
                    "chartStackUnmappedBucket": "from-profile",
                },
            },
            "defaultProfile": "vue_src_tree",
            "projectProfiles": {"api-server": "java_tree"},
        }
        with patch("app.core.module_extract.load_module_grouping", return_value=cfg):
            self.assertEqual(
                module_extract.chart_stack_unmapped_bucket("api-server"),
                "from-profile",
            )

    def test_module_bucket_display_key_only_maps_unknown(self) -> None:
        self.assertEqual(
            module_extract.module_bucket_display_key("portal", "x"),
            "portal",
        )
        cfg = {
            "defaults": {"chartStackUnmappedBucket": "기타"},
            "profiles": {"vue_src_tree": {}},
            "defaultProfile": "vue_src_tree",
            "projectProfiles": {},
        }
        with patch("app.core.module_extract.load_module_grouping", return_value=cfg):
            self.assertEqual(
                module_extract.module_bucket_display_key("unknown", "p"),
                "기타",
            )


if __name__ == "__main__":
    unittest.main()
