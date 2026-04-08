"""웹 issueComponentKey 와 동일한 Python `issue_component_key`."""
from __future__ import annotations

import unittest

from app.core.team_high_risk import issue_component_key


class IssueComponentKeyTests(unittest.TestCase):
    def test_string_component(self) -> None:
        self.assertEqual(
            issue_component_key({"component": " proj:path/Foo.java "}),
            "proj:path/Foo.java",
        )

    def test_main_component_object(self) -> None:
        self.assertEqual(
            issue_component_key({"mainComponent": {"key": "k:src/X.java"}}),
            "k:src/X.java",
        )

    def test_empty(self) -> None:
        self.assertEqual(issue_component_key({}), "")
