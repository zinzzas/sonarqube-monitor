"""표준 severity 하한 → Sonar 네이티브 필터."""
from __future__ import annotations

import unittest

from app.core.severity import (
    parse_severity_floor,
    sonar_native_severities_for_standard_floor,
)


class SeverityFloorTests(unittest.TestCase):
    def test_parse_unknown_is_info(self) -> None:
        self.assertEqual(parse_severity_floor(None), "INFO")
        self.assertEqual(parse_severity_floor(""), "INFO")
        self.assertEqual(parse_severity_floor("  "), "INFO")
        self.assertEqual(parse_severity_floor("nope"), "INFO")

    def test_parse_case_insensitive(self) -> None:
        self.assertEqual(parse_severity_floor("medium"), "MEDIUM")

    def test_floor_medium_includes_bhm(self) -> None:
        self.assertEqual(
            sonar_native_severities_for_standard_floor("MEDIUM"),
            ("BLOCKER", "CRITICAL", "MAJOR"),
        )

    def test_floor_high(self) -> None:
        self.assertEqual(
            sonar_native_severities_for_standard_floor("HIGH"),
            ("BLOCKER", "CRITICAL"),
        )

    def test_floor_info_is_all_native(self) -> None:
        self.assertEqual(
            sonar_native_severities_for_standard_floor("INFO"),
            ("BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"),
        )


if __name__ == "__main__":
    unittest.main()
