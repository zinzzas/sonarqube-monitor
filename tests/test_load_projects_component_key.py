"""componentKey → 프로젝트 행 조회."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.config.load_projects import project_row_by_component_key


class ProjectRowByComponentKeyTests(unittest.TestCase):
    def test_match(self) -> None:
        rows = [
            {"id": "a", "label": "A", "componentKey": "sonar-key-one"},
            {"id": "b", "label": "B", "componentKey": "other"},
        ]
        with patch("app.config.load_projects.load_component_projects", return_value=rows):
            r = project_row_by_component_key("sonar-key-one")
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r["id"], "a")

    def test_no_match(self) -> None:
        with patch("app.config.load_projects.load_component_projects", return_value=[]):
            self.assertIsNone(project_row_by_component_key("missing"))
