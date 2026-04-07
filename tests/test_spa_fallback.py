"""SPA 깊은 경로가 index.html 로 폴백되는지 (Vue Router)."""
from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class SpaFallbackTests(unittest.TestCase):
    def test_deep_path_returns_html_when_dist_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dist = root / "web" / "dist"
        if not dist.is_dir():
            self.skipTest("web/dist 없음 — npm run build 후 검증")
        from main import app

        c = TestClient(app)
        r = c.get("/admin/team-mapping")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
