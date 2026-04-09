"""pathSegmentAny: 디렉터리 세그먼트 정확 일치(파일명 제외)."""
from __future__ import annotations

import unittest

from app.core.module_extract import (
    _directory_segments_for_exclude,
    _match_excludes,
    is_excluded_from_module_rollup,
)


class DirectorySegmentsForExcludeTests(unittest.TestCase):
    def test_strips_trailing_java_file(self) -> None:
        segs = _directory_segments_for_exclude(
            "shrbatch/dashboard/service/DashBoardSaleDataService.java"
        )
        self.assertEqual(segs, ["shrbatch", "dashboard", "service"])

    def test_no_extension_last_segment_kept(self) -> None:
        """확장자 없는 마지막 토큰은 디렉터리로 간주(팀·롤업과 동일 휴리스틱)."""
        segs = _directory_segments_for_exclude("a/b/c")
        self.assertEqual(segs, ["a", "b", "c"])


class PathSegmentAnyTests(unittest.TestCase):
    def test_segment_dashboard_excludes_middle_folder(self) -> None:
        cfg = {
            "pathSegmentAny": ["dashboard"],
            "pathPrefixes": [],
            "pathContains": [],
            "firstSegments": [],
            "fileSuffixes": [],
        }
        rest = "shrbatch/dashboard/service/Foo.java"
        self.assertTrue(_match_excludes(rest, cfg))

    def test_exact_segment_only_not_substring(self) -> None:
        """dashboardThing 과 dashboard 는 다름."""
        cfg = {
            "pathSegmentAny": ["dashboard"],
            "pathPrefixes": [],
            "pathContains": [],
            "firstSegments": [],
            "fileSuffixes": [],
        }
        self.assertFalse(_match_excludes("com/dashboardThing/foo.java", cfg))

    def test_api_server_integration(self) -> None:
        comp = "2856-all:src/main/java/net/cj/shrbatch/dashboard/service/DashBoardSaleDataService.java"
        self.assertTrue(is_excluded_from_module_rollup(comp, "api-server"))

    def test_path_contains_still_substring(self) -> None:
        cfg = {
            "pathSegmentAny": [],
            "pathPrefixes": [],
            "pathContains": ["/mock/"],
            "firstSegments": [],
            "fileSuffixes": [],
        }
        self.assertTrue(_match_excludes("a/b/mock/c.java", cfg))


class OrSemanticsTests(unittest.TestCase):
    def test_prefix_wins_before_segment(self) -> None:
        cfg = {
            "pathPrefixes": ["generated"],
            "pathSegmentAny": ["x"],
            "pathContains": [],
            "firstSegments": [],
            "fileSuffixes": [],
        }
        self.assertTrue(_match_excludes("generated/foo.java", cfg))


if __name__ == "__main__":
    unittest.main()
